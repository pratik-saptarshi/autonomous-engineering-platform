#!/usr/bin/env python3
"""ghg — GitHub gateway.

Task 1: `ghg watch`, the coalescing run watcher. One poller per run,
epoch-fenced through the `watches` table in a shared SQLite ledger;
every other concurrent caller waits and reports the same conclusion.

Task 2: the slim ledger and budget core — the `calls` table, rolling-
window `spend`/`in_flight`, atomic `reserve_all`/`finalize`, the
`rate_limit` `snapshot()` with first-use core seeding, and `classify`.

Later tasks add `ghg run` (Task 3) and `ghg check` / `ghg status`
(Task 4). The interfaces those tasks consume are fixed here:
`open_db()`, `gated_gh(argv, actor)`, and the `watches` schema.

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


# ------------------------------------------------------- budget ledger

DEFAULT_LIMITS = {
    "core": [(3600, 3500)],
    "graphql": [(3600, 3500)],  # cost units: flat 2 per invocation
    "search": [(60, 20)],
    "code_search": [(60, 9)],
    "content": [(60, 40), (3600, 300)],
}
LIMITS = {bucket: list(pairs) for bucket, pairs in DEFAULT_LIMITS.items()}

OUTCOMES = {"reserved", "ok", "error", "denied", "bypass",
            "ungated_error", "abandoned"}
TERMINAL_OUTCOMES = OUTCOMES - {"reserved"}
RESERVATION_TTL_S = 600  # reservations older than 10 min are reaped
SNAPSHOT_TTL_S = 60

CALLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls(
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    actor TEXT NOT NULL,
    bucket TEXT NOT NULL,
    cost INTEGER NOT NULL,
    argv TEXT NOT NULL,
    outcome TEXT
)
"""
CALLS_INDEX = ("CREATE INDEX IF NOT EXISTS calls_bucket_ts"
               " ON calls(bucket, ts)")
META_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT
)
"""


class GateBroken(Exception):
    """The gateway's own state is unusable (DB error, lock timeout).

    Never a budget denial: Task 3 turns this into a fail-open
    pass-through with an `ungated_error` trace.
    """


def load_limits():
    """Bucket -> [(window_s, cap)], overridable via GHG_LIMITS_JSON."""
    raw = os.environ.get("GHG_LIMITS_JSON")
    if raw:
        try:
            parsed = json.loads(raw)
            return {str(bucket): [(int(w), int(c)) for w, c in pairs]
                    for bucket, pairs in parsed.items()}
        except (ValueError, TypeError):
            pass  # a broken override must not widen the caps
    return {bucket: list(pairs)
            for bucket, pairs in DEFAULT_LIMITS.items()}


# ------------------------------------------------------------ classify

_MUTATING_SUBCOMMANDS = {"create", "comment", "merge", "edit", "close",
                         "reopen", "review", "label", "upload", "delete"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_API_PARAM_FLAGS = {"-f", "--field", "-F", "--raw-field", "--input"}


def _is_mutating(argv):
    if len(argv) >= 2 and argv[1] in _MUTATING_SUBCOMMANDS:
        return True
    if argv[0] == "workflow" and len(argv) >= 2 and argv[1] == "run":
        return True
    if argv[0] == "api":
        for i, tok in enumerate(argv):
            if tok in ("-X", "--method"):
                if (i + 1 < len(argv)
                        and argv[i + 1].upper() in _MUTATING_METHODS):
                    return True
            elif tok.startswith("--method="):
                if tok.split("=", 1)[1].upper() in _MUTATING_METHODS:
                    return True
            elif (tok.startswith("-X") and len(tok) > 2
                    and tok[2:].upper() in _MUTATING_METHODS):
                return True
            elif tok in _API_PARAM_FLAGS:
                return True
            elif (tok.startswith("--field=")
                    or tok.startswith("--raw-field=")
                    or tok.startswith("--input=")):
                return True
            elif (tok.startswith("-f") or tok.startswith("-F")) \
                    and len(tok) > 2 and not tok.startswith("--"):
                return True  # combined spelling, e.g. -fname=y
    return False


def classify(argv):
    """Exact decision table: argv -> [(bucket, cost), ...].

    Exactly one primary bucket; a `(content, 1)` charge is appended
    when a mutating signal is present. The fan-out modifier (x5) is a
    deliberate conservative proxy: `--paginate` under-counts unbounded
    page counts, `--log` over-counts the common single-download case.
    """
    argv = [str(a) for a in argv]
    if argv and argv[0] == "gh":
        argv = argv[1:]
    if not argv:
        return []
    if argv[0] == "search":
        bucket, cost = ("code_search", 1) if (
            len(argv) >= 2 and argv[1] == "code") else ("search", 1)
    elif argv[0] in ("pr", "issue") and len(argv) >= 2 \
            and argv[1] in ("view", "list"):
        bucket, cost = "graphql", 2
    elif argv[0] == "api" and len(argv) >= 2 \
            and argv[1].strip("/") == "graphql":
        bucket, cost = "graphql", 2
    else:
        bucket, cost = "core", 1
    if any(tok == "--paginate" or tok.startswith("--paginate=")
           or tok in ("--log", "--log-failed")
           or tok.startswith("--log=") for tok in argv):
        cost *= 5
    charges = [(bucket, cost)]
    if _is_mutating(argv):
        charges.append(("content", 1))
    return charges


# ------------------------------------------------------------ redaction

_REDACT_FLAGS = {"--body", "--title", "-m", "--message", "--body-file"}


def redact_argv(argv):
    """Join argv for ledger storage, redacting sensitive flag values.

    The values of --body, --title, -m/--message and --body-file are
    replaced by `<redacted len=N>` in both spellings (`--body text`
    and `--body=text`). Response bodies/credentials are never stored.
    """
    argv = [str(a) for a in argv]
    out = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in _REDACT_FLAGS:
            out.append(tok)
            if i + 1 < len(argv):
                out.append("<redacted len=%d>" % len(argv[i + 1]))
                i += 2
            else:
                i += 1
            continue
        if "=" in tok:
            flag, value = tok.split("=", 1)
            if flag in _REDACT_FLAGS:
                out.append("%s=<redacted len=%d>" % (flag, len(value)))
                i += 1
                continue
        if tok.startswith("-m") and not tok.startswith("--") \
                and len(tok) > 2:
            out.append("-m<redacted len=%d>" % len(tok[2:]))
            i += 1
            continue
        out.append(tok)
        i += 1
    return " ".join(out)


# --------------------------------------------------------------- ledger

class Ledger:
    """The slim call ledger over the shared ghg DB (Task 1 helper)."""

    def __init__(self, source=None):
        if isinstance(source, sqlite3.Connection):
            self.conn = source
            self._owns_conn = False
        elif source is None:
            self.conn = open_db(db_path())
            self._owns_conn = True
        else:
            self.conn = open_db(source)
            self._owns_conn = True
        self.limits = load_limits()
        self.last_denial = None
        self._ensure_schema()

    def close(self):
        if self._owns_conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _ensure_schema(self):
        for attempt in range(10):
            try:
                self.conn.execute(CALLS_SCHEMA)
                self.conn.execute(CALLS_INDEX)
                self.conn.execute(META_SCHEMA)
                return
            except sqlite3.OperationalError as exc:
                if _is_busy(exc) and attempt < 9:
                    time.sleep(0.1 + random.uniform(0, 0.1))
                    continue
                raise GateBroken(str(exc)) from exc

    # -- meta -----------------------------------------------------------

    def meta_get(self, key):
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row is not None else None

    def meta_set(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, str(value)))

    # -- spend ----------------------------------------------------------

    def _active_seed(self, now):
        """(seed_core, seeded_at, seed_reset) while the seed applies."""
        try:
            seed_core = self.meta_get("seed_core")
            seeded_at = self.meta_get("seeded_at")
            seed_reset = self.meta_get("seed_reset")
            if seed_core is None or seeded_at is None \
                    or seed_reset is None:
                return None
            if int(seed_reset) <= now:
                return None
            return int(seed_core), int(seeded_at), int(seed_reset)
        except (ValueError, TypeError):
            return None

    def _sum(self, bucket, outcome_clause, since):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM calls"
            " WHERE bucket = ? AND outcome IN %s AND ts > ?"
            % outcome_clause, (bucket, since)).fetchone()
        return int(row[0])

    def spend(self, bucket, window_s, now=None):
        """Terminal spend inside the rolling window (never reserved).

        For `core` under an active seed, the effective spend is
        seed_core + ledger spend accrued after seeded_at.
        """
        now = int(time.time()) if now is None else int(now)
        since = now - int(window_s)
        if bucket == "core":
            seed = self._active_seed(now)
            if seed is not None:
                seed_core, seeded_at, _ = seed
                return seed_core + self._sum(
                    bucket, "('ok', 'error', 'bypass')",
                    max(since, seeded_at))
        return self._sum(bucket, "('ok', 'error', 'bypass')", since)

    def in_flight(self, bucket, window_s, now=None):
        """Reserved (non-terminal) cost inside the rolling window."""
        now = int(time.time()) if now is None else int(now)
        return self._sum(bucket, "('reserved')", now - int(window_s))

    # -- reserve / finalize ----------------------------------------------

    def reap_abandoned(self, now=None):
        """Reservations older than 10 min become `abandoned`.

        DB/lock failures surface as GateBroken (the sole failure
        signal Task 3 keys its fail-open on), never as a raw sqlite3
        error — including on the reserve_all entry path, which calls
        this before its own BUSY-retry handling.
        """
        now = int(time.time()) if now is None else int(now)
        try:
            cur = self.conn.execute(
                "UPDATE calls SET outcome = 'abandoned'"
                " WHERE outcome = 'reserved' AND ts < ?",
                (now - RESERVATION_TTL_S,))
        except sqlite3.OperationalError as exc:
            raise GateBroken(str(exc)) from exc
        return cur.rowcount

    def reserve_all(self, charges, actor, argv, now=None):
        """Atomically reserve every charge, or none.

        Returns the reserved row ids, or None on denial (exactly one
        `denied` row, cost 0, is written for the denying bucket).
        Raises GateBroken on DB/lock failure — never a denial.
        """
        now = int(time.time()) if now is None else int(now)
        argv_text = argv if isinstance(argv, str) \
            else redact_argv(list(argv))
        charges = [(str(b), int(c)) for b, c in charges]
        self.reap_abandoned(now=now)
        for attempt in range(8):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                if _is_busy(exc) and attempt < 7:
                    time.sleep(0.1 + random.uniform(0, 0.1))
                    continue
                raise GateBroken(str(exc)) from exc
            try:
                added = {}
                denial = None
                for bucket, cost in charges:
                    for window_s, cap in self.limits.get(bucket, []):
                        used = self.spend(bucket, window_s, now=now) \
                            + self.in_flight(bucket, window_s, now=now) \
                            + added.get(bucket, 0)
                        if used + cost > cap:
                            denial = (bucket, window_s, cap)
                            break
                    if denial is not None:
                        break
                    added[bucket] = added.get(bucket, 0) + cost
                if denial is not None:
                    bucket, window_s, cap = denial
                    self.conn.execute(
                        "INSERT INTO calls"
                        " (ts, actor, bucket, cost, argv, outcome)"
                        " VALUES (?, ?, ?, 0, ?, 'denied')",
                        (now, actor, bucket, argv_text))
                    self.conn.execute("COMMIT")
                    self.last_denial = {
                        "bucket": bucket, "window_s": window_s,
                        "cap": cap, "reset": now + window_s}
                    return None
                ids = []
                for bucket, cost in charges:
                    cur = self.conn.execute(
                        "INSERT INTO calls"
                        " (ts, actor, bucket, cost, argv, outcome)"
                        " VALUES (?, ?, ?, ?, ?, 'reserved')",
                        (now, actor, bucket, cost, argv_text))
                    ids.append(cur.lastrowid)
                self.conn.execute("COMMIT")
                self.last_denial = None
                return ids
            except sqlite3.OperationalError as exc:
                try:
                    self.conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                if _is_busy(exc) and attempt < 7:
                    time.sleep(0.1 + random.uniform(0, 0.1))
                    continue
                raise GateBroken(str(exc)) from exc
            except Exception:
                try:
                    self.conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise

    def finalize(self, row_ids, outcome):
        """Move reserved rows to a terminal outcome."""
        if outcome not in TERMINAL_OUTCOMES:
            raise ValueError("not a terminal outcome: %r" % (outcome,))
        try:
            for row_id in row_ids:
                self.conn.execute(
                    "UPDATE calls SET outcome = ? WHERE id = ?",
                    (outcome, int(row_id)))
        except sqlite3.OperationalError as exc:
            raise GateBroken(str(exc)) from exc

    # -- snapshot ---------------------------------------------------------

    def _fetch_rate_limit(self):
        try:
            proc = subprocess.run(
                [real_gh(), "api", "rate_limit"],
                capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def _maybe_seed(self, payload, now):
        """First-use seeding, core only (see the Task 2 brief).

        Seeds from a fresh snapshot whenever no live seed is on
        record — the fresh-DB case the plan names, and equally the
        first snapshot after an earlier seed's reset has passed.
        Effective core spend then counts seed + post-seed ledger
        spend only (see spend()), so nothing is double-counted.
        """
        if self._active_seed(now) is not None:
            return
        core = None
        resources = payload.get("resources")
        if isinstance(resources, dict):
            core = resources.get("core")
        if not isinstance(core, dict):
            core = payload.get("rate")
        if not isinstance(core, dict):
            return
        try:
            used = int(core["used"])
            reset = int(core["reset"])
        except (KeyError, ValueError, TypeError):
            return
        self.meta_set("seed_core", used)
        self.meta_set("seeded_at", now)
        self.meta_set("seed_reset", reset)

    def snapshot(self, force=False):
        """Cached `rate_limit` JSON (TTL 60 s), or None.

        Ungated, unledgered, failure-tolerant: a failed fetch keeps
        the stale cache and writes no `calls` row.
        """
        now = int(time.time())
        cached_raw = self.meta_get("rate_limit")
        fetched_at = self.meta_get("rate_limit_fetched_at")
        if cached_raw and fetched_at and not force:
            try:
                if now - int(fetched_at) < SNAPSHOT_TTL_S:
                    return json.loads(cached_raw)
            except (ValueError, TypeError):
                pass
        payload = self._fetch_rate_limit()
        if payload is None:
            if cached_raw:
                try:
                    return json.loads(cached_raw)
                except ValueError:
                    return None
            return None
        self.meta_set("rate_limit", json.dumps(payload))
        self.meta_set("rate_limit_fetched_at", now)
        self._maybe_seed(payload, now)
        return payload


def snapshot(ledger=None):
    """Module-level convenience: snapshot() on a default Ledger."""
    if ledger is None:
        with Ledger() as owned:
            return owned.snapshot()
    return ledger.snapshot()


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
    try:  # housekeeping: reap stale reservations (Task 2 core)
        Ledger(conn).reap_abandoned()
    except Exception:
        pass  # housekeeping must never break the watch itself
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
