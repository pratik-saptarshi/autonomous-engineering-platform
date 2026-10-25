#!/usr/bin/env python3
"""ghg — GitHub gateway.

Task 1: `ghg watch`, the coalescing run watcher. One poller per run,
epoch-fenced through the `watches` table in a shared SQLite ledger;
every other concurrent caller waits and reports the same conclusion.

Later tasks add the budget ledger core (Task 2), `ghg run` (Task 3),
and `ghg check` / `ghg status` (Task 4). The interfaces those tasks
consume are fixed here: `open_db()`, `gated_gh(argv, actor)`, and the
`watches` schema.

Python 3 standard library only. Runtime state lives in $GHG_STATE_DIR
(default ~/workspace/ghg-state), never in the source tree (ruling R5).
"""

import argparse
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

DEFAULT_INTERVAL_FLOOR = 45
DEFAULT_TIMEOUT = 1800

WATCHES_SCHEMA = """
CREATE TABLE IF NOT EXISTS watches(
    run_key TEXT PRIMARY KEY,
    epoch INTEGER NOT NULL,
    poller TEXT NOT NULL,
    heartbeat INTEGER NOT NULL,
    status TEXT,
    conclusion TEXT,
    updated INTEGER NOT NULL
)
"""


# ---------------------------------------------------------------- seams

def state_dir():
    env = os.environ.get("GHG_STATE_DIR")
    if env:
        return Path(env)
    return Path.home() / "workspace" / "ghg-state"


def db_path():
    return state_dir() / "ghg.db"


def real_gh():
    """The one seam through which every real `gh` call resolves."""
    return os.environ.get("GHG_REAL_GH") or "/usr/bin/gh"


def interval_floor():
    env = os.environ.get("GHG_MIN_INTERVAL")
    if env:
        return float(env)
    return float(DEFAULT_INTERVAL_FLOOR)


def resolve_actor():
    env = os.environ.get("GHG_ACTOR")
    if env:
        return env
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5)
        if top.returncode == 0 and top.stdout.strip():
            return os.path.basename(top.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def gated_gh(argv, actor, timeout=None):
    """Run the real `gh` with `argv`; return (exit code, stdout).

    Task 1: a direct pass-through. Task 3 swaps in the budget gate
    behind this same signature. A subprocess timeout is reported as
    exit code 124 with no output (an inconclusive poll, never a write).
    """
    try:
        proc = subprocess.run(
            [real_gh()] + list(argv),
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError:
        return 127, ""
    return proc.returncode, proc.stdout


# ------------------------------------------------------------------ db

def open_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    # journal_mode flips the whole database file: two processes opening
    # a fresh DB in the same instant can still collide here, so the
    # WAL switch + schema creation get the same bounded BUSY retry as
    # the claim path.
    for attempt in range(5):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(WATCHES_SCHEMA)
            break
        except sqlite3.OperationalError as exc:
            if _is_busy(exc) and attempt < 4:
                time.sleep(0.1 + random.uniform(0, 0.1))
                continue
            raise
    return conn


def _is_busy(exc):
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def get_row(conn, run_key):
    return conn.execute(
        "SELECT run_key, epoch, poller, heartbeat, status, conclusion,"
        " updated FROM watches WHERE run_key = ?",
        (run_key,)).fetchone()


# ------------------------------------------------------------- claiming

def try_claim(conn, run_key, self_id, interval):
    """One claim/takeover attempt, exactly per the plan protocol.

    Returns (True, epoch) if this caller is (now) the poller,
    (False, None) otherwise. Completed rows are never taken over.
    """
    for attempt in range(3):
        try:
            conn.execute("BEGIN IMMEDIATE")
            break
        except sqlite3.OperationalError as exc:
            if _is_busy(exc) and attempt < 2:
                time.sleep(0.1 + random.uniform(0, 0.1))
                continue
            return False, None
    try:
        now = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO watches"
            " (run_key, epoch, poller, heartbeat, status, conclusion,"
            "  updated) VALUES (?, 1, ?, ?, NULL, NULL, ?)",
            (run_key, self_id, now, now))
        row = get_row(conn, run_key)
        if row is None or row["status"] == "completed":
            conn.execute("COMMIT")
            return False, None
        if row["poller"] == self_id:
            conn.execute("COMMIT")
            return True, row["epoch"]
        if now - row["heartbeat"] > 2 * interval:
            cur = conn.execute(
                "UPDATE watches SET poller = ?, epoch = epoch + 1,"
                " heartbeat = ?, updated = ?"
                " WHERE run_key = ? AND epoch = ?"
                " AND (status IS NULL OR status <> 'completed')",
                (self_id, now, now, run_key, row["epoch"]))
            if cur.rowcount == 1:
                conn.execute("COMMIT")
                return True, row["epoch"] + 1
        conn.execute("COMMIT")
        return False, None
    except sqlite3.OperationalError:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        return False, None


# -------------------------------------------------------------- polling

def refresh_heartbeat(conn, run_key, self_id, epoch):
    """Poller duty (ii). False means fencing loss."""
    cur = conn.execute(
        "UPDATE watches SET heartbeat = ?, updated = ?"
        " WHERE run_key = ? AND poller = ? AND epoch = ?",
        (int(time.time()), int(time.time()), run_key, self_id, epoch))
    return cur.rowcount == 1


def write_status(conn, run_key, self_id, epoch, status, conclusion):
    """Poller duty (iv), epoch-guarded like (ii). False = fenced."""
    cur = conn.execute(
        "UPDATE watches SET status = ?, conclusion = ?, updated = ?"
        " WHERE run_key = ? AND poller = ? AND epoch = ?",
        (status, conclusion, int(time.time()), run_key, self_id, epoch))
    return cur.rowcount == 1


def poll_once(conn, run_key, repo, run_id, self_id, epoch, interval,
              actor):
    """One poller cycle: duties (i)-(iv) from the plan, in order.

    Returns 'completed', 'polled' (no terminal state yet, including an
    inconclusive poll), 'fenced', or 'denied'.
    """
    row = get_row(conn, run_key)  # (i) fencing re-check
    if row is None or row["poller"] != self_id or row["epoch"] != epoch:
        return "fenced"
    if row["status"] == "completed":
        return "completed"
    if not refresh_heartbeat(conn, run_key, self_id, epoch):  # (ii)
        return "fenced"
    code, out = gated_gh(  # (iii)
        ["run", "view", str(run_id), "--repo", repo,
         "--json", "status,conclusion"],
        actor, timeout=max(interval - 5, 1))
    if code == 75:  # ruling R1: a gate denial ends the watch
        line = out.strip() or "ghg: DENIED"
        print(line, file=sys.stderr, flush=True)
        return "denied"
    if code != 0:
        return "polled"  # inconclusive: no write, retry next cycle
    try:
        payload = json.loads(out)
        status = payload["status"]
        conclusion = payload.get("conclusion")
    except (ValueError, KeyError, AttributeError):
        return "polled"
    if not write_status(conn, run_key, self_id, epoch, status,
                        conclusion):  # (iv)
        return "fenced"
    if status == "completed":
        return "completed"
    return "polled"


# ---------------------------------------------------------------- watch

def _fmt_num(value):
    return "%g" % value


def cmd_watch(args):
    floor = interval_floor()
    requested = args.interval if args.interval is not None else floor
    effective = requested
    if effective < floor:
        print("ghg watch: interval %ss is below the %ss floor;"
              " using %ss" % (_fmt_num(requested), _fmt_num(floor),
                              _fmt_num(floor)),
              file=sys.stderr, flush=True)
        effective = floor
    run_id = args.run
    run_key = "%s#%s" % (args.repo, run_id)
    self_id = "%d-%s" % (os.getpid(), uuid.uuid4().hex[:12])
    actor = resolve_actor()
    conn = open_db(db_path())
    deadline = time.monotonic() + args.timeout
    is_poller = False
    epoch = None

    def remaining():
        return deadline - time.monotonic()

    while True:
        if remaining() <= 0:
            print("ghg watch: run %s timeout after %ss"
                  % (run_id, _fmt_num(args.timeout)), flush=True)
            return 1
        row = get_row(conn, run_key)
        if row is not None and row["status"] == "completed":
            print("ghg watch: run %s completed conclusion=%s"
                  % (run_id, row["conclusion"]), flush=True)
            return 0 if row["conclusion"] == "success" else 1
        if not is_poller:
            claimed, claimed_epoch = try_claim(conn, run_key, self_id,
                                               effective)
            if claimed:
                is_poller = True
                epoch = claimed_epoch
            else:
                time.sleep(min(0.2, max(0.0, remaining())))
                continue
        outcome = poll_once(conn, run_key, args.repo, run_id, self_id,
                            epoch, effective, actor)
        if outcome == "denied":
            return 75
        if outcome == "fenced":
            is_poller = False
            epoch = None
            continue
        if outcome == "completed":
            continue  # loop head prints the final line from the row
        time.sleep(min(effective, max(0.0, remaining())))


# ------------------------------------------------------------------ cli

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ghg", description="ghg — GitHub gateway")
    sub = parser.add_subparsers(dest="verb", required=True)
    watch = sub.add_parser("watch", help="coalesced `gh run` watcher")
    watch.add_argument("--repo", required=True)
    watch.add_argument("--run", required=True)
    watch.add_argument("--interval", type=float, default=None)
    watch.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    if args.verb == "watch":
        return cmd_watch(args)
    parser.error("unknown verb: %s" % args.verb)
    return 2


if __name__ == "__main__":
    sys.exit(main())
