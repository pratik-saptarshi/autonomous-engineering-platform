#!/usr/bin/env python3
"""
OpenCode-OpenChamber bridge — session dispatcher.

Drives ONE bounded worker task as an OpenCode session through the
OpenCode background service's API, so the task appears in OpenChamber
as a titled session with a full transcript.

Route (the ONLY route — `opencode run` hangs in this VM, never use it):
    health/wake:  opencode api GET  /api/session
    create:       opencode api POST /api/session
                  {title, location:{directory}, model:{id, providerID}, agent}
    prompt:       opencode api POST /api/session/<id>/prompt   {text}
    poll:         opencode api GET  /api/session/<id>
                  opencode api GET  /api/session/<id>/message
    harvest:      verify the report file; if absent, extract the final
                  assistant message into the report path, marked
                  harvested-not-authored, and flag the task unreported.

All API calls go through the `opencode api` CLI, which attaches the
service credentials itself — this script never reads the service
password file.

The no-push / no-post rules carried in the brief footer are DETECTIVE,
not preventive: sessions run with the user's filesystem and shell
access. The dispatcher records the worktree git HEAD + dirty-file
count before and after (local only, no network) and appends a ledger
entry; the controller still diffs remote refs and checks the ghg
ledger Muse-side before anything is published.

Exit codes:
    0  session completed (idle) and report harvested
    2  service health/wake failed
    3  stall declared (bounded waits, no progress) — partial harvested;
       the session is interrupted and confirmed idle before returning
    4  overall timeout — partial harvested; same interrupt + confirm
       (if a stop cannot be confirmed, the record carries
       session_stop_unconfirmed and the controller must NOT re-dispatch
       until the session is confirmed idle)
    5  session completed but report missing/trivial (harvested fallback
       written); controller must treat the task as UNREPORTED
    6  session ended with outcome=failed/interrupted
    64 usage / input error
"""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent
FOOTER_PATH = BRIDGE_DIR / "brief-footer.txt"


def bridge_home() -> Path:
    """The bridge's runtime data home — where the dispatch ledger lives.

    Resolution order: $OPENCHAMBER_BRIDGE_HOME (exported by the VM's
    setup initialization; see env.sh in this kit) when set, else this
    script's own directory. Kit-internal files (brief footer, template)
    always resolve relative to this script, never via the variable.
    """
    env = os.environ.get("OPENCHAMBER_BRIDGE_HOME")
    return Path(env).expanduser().resolve() if env else BRIDGE_DIR

# Model allowlist — Pratik's standing rule for the bridge (2026-11-20,
# expanded 2026-11-21): ONLY these models may be dispatched. Enforced
# here, not by convention. IDs verified live in `opencode models`.
ALLOWED_MODELS = {
    "opencode-go/deepseek-v4.1-flash",       # DeepSeek V4.1 Flash
    "opencode-go/glm-5.3-flash",             # GLM-5.3-Flash
    "opencode-go/minimax-m3.1-flash",        # MiniMax M3.1 Flash
    "opencode-go/muse-spark-1.3-contributor",  # Muse Spark 1.3 (contributor)
    "opencode-go/hy4-flash-free",            # Hy4 Flash Free
    "opencode-go/iceman-contributor-free",   # Iceman (contributor, free)
    "opencode-go/longcat-2.5-free",          # LongCat 2.5 Free
    "opencode-go/beam-free",                 # Beam Free
    "opencode/tidepool-alpha-free",          # Tidepool Alpha Free — NOTE: listed
    # only under the `opencode` provider; no opencode-go variant exists.
}
DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"


def find_opencode() -> str:
    p = shutil.which("opencode")
    if p:
        return p
    cand = Path.home() / ".opencode" / "bin" / "opencode"
    if cand.exists():
        return str(cand)
    raise SystemExit("opencode binary not found on PATH or at ~/.opencode/bin/opencode")


OPENCODE = None  # set in main


def api(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
    cmd = [OPENCODE, "api", method, path]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"opencode api {method} {path} rc={r.returncode}: "
                           f"{(r.stderr or out)[:500]}")
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise RuntimeError(f"opencode api {method} {path}: non-JSON output: {out[:300]}")


def health_wake(attempts: int = 3) -> list:
    """GET /api/session doubles as the wake route (documented, TOOLS.md)."""
    last = None
    for i in range(attempts):
        try:
            res = api("GET", "/api/session", timeout=90)
            return res.get("data", [])
        except Exception as e:  # service may need a moment to come up
            last = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"health/wake failed after {attempts} attempts: {last}")


def git_snapshot(workdir: Path) -> dict:
    def g(*args):
        r = subprocess.run(["git", "-C", str(workdir), *args],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    head = g("rev-parse", "HEAD")
    if head is None:
        return {"git": False}
    status = g("status", "--porcelain")
    if status is None:
        # A failed status command means the worktree state is UNKNOWN;
        # recording 0 dirty files would read as "clean" (Sourcery, PR #213).
        return {"git": True, "head": head, "dirty_files": None,
                "git_status_error": True}
    return {"git": True, "head": head,
            "dirty_files": 0 if not status else len(status.splitlines())}


def final_assistant_text(messages: list) -> str:
    """Messages arrive newest-first; find the newest assistant text."""
    for m in messages:
        if m.get("type") == "assistant":
            parts = [c.get("text", "") for c in m.get("content", [])
                     if c.get("type") == "text"]
            text = "\n".join(p for p in parts if p).strip()
            if text:
                return text
    return ""


FALLBACK_MARKER = ("<!-- HARVESTED-NOT-AUTHORED: the session ended without writing "
                   "its report file. The text below is the final assistant message "
                   "extracted by dispatch.py. The controller must treat this task "
                   "as UNREPORTED. -->")


def report_snapshot(report_path: Path) -> dict:
    """State of the report path BEFORE this dispatch runs. Harvest
    authorship is judged against this snapshot: a file counts as
    authored by the current session only if this dispatch created it
    or changed its content. A pre-existing file the session never
    touched — a stale report from an earlier dispatch, or this
    dispatcher's own fallback from a previous run — is never accepted
    as authored (Codex P1 on PR #213)."""
    if not report_path.exists():
        return {"existed": False, "bytes": 0, "sha256": None}
    data = report_path.read_bytes()
    return {"existed": True, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def harvest(session_id: str, report_path: Path, min_bytes: int,
            messages: list, pre: dict) -> dict:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists() and report_path.stat().st_size >= min_bytes:
        data = report_path.read_bytes()
        changed = (not pre["existed"]
                   or hashlib.sha256(data).hexdigest() != pre["sha256"])
        is_fallback = data.lstrip().startswith(FALLBACK_MARKER.encode())
        if changed and not is_fallback:
            return {"report": str(report_path),
                    "report_bytes": report_path.stat().st_size,
                    "report_authored": True,
                    "report_preexisting": pre["existed"]}
    # Before the fallback overwrites the path: a genuine pre-existing
    # report (e.g. the earlier attempt a retry is replacing) is preserved
    # beside it, never destroyed (Sourcery, PR #213). A previous fallback
    # is not preserved — it carries no authored content.
    preserved = None
    if report_path.exists():
        current = report_path.read_bytes()
        if not current.lstrip().startswith(FALLBACK_MARKER.encode()):
            preserved = report_path.with_name(
                report_path.name + ".prior-" + time.strftime("%Y%m%dT%H%M%S"))
            preserved.write_bytes(current)
    text = final_assistant_text(messages)
    report_path.write_text(FALLBACK_MARKER + "\n\n"
                           + (text or "(no assistant text found in transcript)") + "\n")
    result = {"report": str(report_path), "report_bytes": report_path.stat().st_size,
              "report_authored": False, "report_preexisting": pre["existed"]}
    if preserved is not None:
        result["report_prior_preserved"] = str(preserved)
    return result


def stop_session(session_id: str, confirm_seconds: int = 30) -> dict:
    """Interrupt a still-running session and confirm it went idle.

    Used on the stall/timeout/prompt-failure exits: returning while the
    worker keeps running lets a re-dispatch collide with it in the
    same worktree (Codex P1 on PR #213). POST .../interrupt is the
    service's stop route (verified live on OpenCode 2.4.1: the record
    gains time.idle and outcome=interrupted)."""
    result = {"session_stopped": False}
    try:
        api("POST", f"/api/session/{session_id}/interrupt", timeout=30)
    except Exception as e:
        result["session_stop_error"] = str(e)
        return result
    deadline = time.time() + confirm_seconds
    while time.time() < deadline:
        try:
            info = api("GET", f"/api/session/{session_id}", timeout=30).get("data", {})
        except Exception:
            info = {}
        if info.get("time", {}).get("idle") or info.get("outcome"):
            result["session_stopped"] = True
            result["session_outcome"] = info.get("outcome")
            return result
        time.sleep(2)
    return result


def main() -> int:
    global OPENCODE
    ap = argparse.ArgumentParser(description="Dispatch one OpenCode session from a brief file.")
    ap.add_argument("--brief", required=True, help="Brief file (its text is the task).")
    ap.add_argument("--workdir", required=True, help="Session location.directory (worktree).")
    ap.add_argument("--title", required=True,
                    help="Session title, convention: '<repo> PR<n> · W<wave> <role> · <base>..<head>'")
    ap.add_argument("--report", required=True, help="Expected report file path (the contract).")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="provider/model-id. Allowlist only (Pratik's rule, 2026-11-20, "
                         "expanded 2026-11-21) — see ALLOWED_MODELS in this file. "
                         "Default: deepseek-v4.1-flash.")
    ap.add_argument("--agent", default="build")
    ap.add_argument("--ledger", default=str(bridge_home() / "ledger.jsonl"),
                    help="JSONL ledger to append the dispatch record to "
                         "(default: ledger.jsonl in $OPENCHAMBER_BRIDGE_HOME, "
                         "else beside this script).")
    ap.add_argument("--archive-brief", default=None,
                    help="Where to archive the adapted brief (default: <report>.brief.md).")
    ap.add_argument("--timeout", type=int, default=1800, help="Overall poll budget, seconds.")
    ap.add_argument("--stall-seconds", type=int, default=600,
                    help="No new message and no session update for this long = stall.")
    ap.add_argument("--poll-seconds", type=int, default=10)
    ap.add_argument("--min-report-bytes", type=int, default=100)
    ap.add_argument("--no-footer", action="store_true", help="Send the brief verbatim, no footer.")
    args = ap.parse_args()

    brief_path = Path(args.brief).expanduser().resolve()
    workdir = Path(args.workdir).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve()
    if not brief_path.exists():
        print(f"brief not found: {brief_path}", file=sys.stderr); return 64
    if not workdir.is_dir():
        print(f"workdir not a directory: {workdir}", file=sys.stderr); return 64
    if len(args.title) > 140:
        print("title too long (>140 chars); keep the board readable", file=sys.stderr); return 64
    if "/" not in args.model:
        print("--model must be provider/model-id", file=sys.stderr); return 64
    if args.model not in ALLOWED_MODELS:
        print(f"model not on the bridge allowlist (Pratik's rule, 2026-11-20): {args.model}\n"
              f"allowed: {', '.join(sorted(ALLOWED_MODELS))}", file=sys.stderr); return 64
    provider, model_id = args.model.split("/", 1)
    archive = Path(args.archive_brief).expanduser().resolve() if args.archive_brief \
        else report_path.with_suffix(report_path.suffix + ".brief.md")
    if archive == report_path:
        print("--archive-brief must not alias --report: the archive write "
              "would destroy the report before the session runs", file=sys.stderr)
        return 64

    OPENCODE = find_opencode()
    started = time.time()
    ledger_rec = {
        "ts_start": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "title": args.title, "model": args.model, "agent": args.agent,
        "workdir": str(workdir), "brief": str(brief_path),
        "report": str(report_path), "git_before": git_snapshot(workdir),
    }

    def finish(code: int, **extra):
        ledger_rec["event"] = "dispatch_finished"
        ledger_rec.update(extra)
        ledger_rec["wall_seconds"] = round(time.time() - started, 1)
        ledger_rec["git_after"] = git_snapshot(workdir)
        Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
        with open(args.ledger, "a") as f:
            f.write(json.dumps(ledger_rec) + "\n")
        print(json.dumps(ledger_rec, indent=1))
        return code

    # 0. one live dispatch per worktree: a second dispatcher on the same
    # worktree could interleave edits and corrupt the shared report and
    # brief archive (Sourcery, PR #213). The flock is released by the OS
    # when this process exits or dies, so a killed dispatcher never
    # wedges the worktree.
    lock_dir = bridge_home() / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / (hashlib.sha256(str(workdir).encode()).hexdigest()[:16] + ".lock")
    lock_fh = open(lock_path, "a+")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return finish(2, status="lock_contended", workdir_lock=str(lock_path))
    ledger_rec["workdir_lock"] = str(lock_path)

    # 1. health / wake
    try:
        health_wake()
    except Exception as e:
        return finish(2, status="health_failed", error=str(e))

    # 2. adapt brief (brief as-is + standard footer) and archive it
    brief_text = brief_path.read_text()
    if not args.no_footer:
        footer = FOOTER_PATH.read_text().replace("{REPORT_PATH}", str(report_path)) \
                                      .replace("{WORKDIR}", str(workdir))
        brief_text = brief_text.rstrip() + "\n\n" + footer
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(brief_text)
    ledger_rec["brief_archived"] = str(archive)

    # 2b. snapshot the report path BEFORE the session exists: harvest
    # authorship is judged against this state, never mere existence.
    pre_dispatch_report = report_snapshot(report_path)
    ledger_rec["report_pre_dispatch"] = pre_dispatch_report

    # 3. create session
    try:
        created = api("POST", "/api/session", {
            "title": args.title,
            "location": {"directory": str(workdir)},
            "model": {"id": model_id, "providerID": provider},
            "agent": args.agent,
        })
    except Exception as e:
        return finish(2, status="create_failed", error=str(e))
    session = created.get("data", {})
    sid = session.get("id")
    if not sid:
        return finish(2, status="create_failed", error=f"no session id in: {created}")
    ledger_rec["session_id"] = sid
    print(f"session created: {sid} — {args.title}", file=sys.stderr)
    # Persist the session id NOW, not only in finish(): if this
    # dispatcher is killed mid-run, the session stays findable in the
    # ledger instead of running untracked (Sourcery, PR #213; the
    # 2026-11-21 manual-harvest incident).
    Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
    with open(args.ledger, "a") as f:
        f.write(json.dumps({"event": "session_created", "session_id": sid,
                            "ts_start": ledger_rec["ts_start"],
                            "title": args.title, "model": args.model,
                            "workdir": str(workdir),
                            "report": str(report_path)}) + "\n")

    # 4. prompt
    prompt_ms = int(time.time() * 1000)
    try:
        api("POST", f"/api/session/{sid}/prompt", {"text": brief_text}, timeout=180)
    except Exception as e:
        stop = stop_session(sid)
        if not stop["session_stopped"]:
            stop["session_stop_unconfirmed"] = True
            print(f"WARNING: session {sid} could not be confirmed stopped; "
                  "do NOT re-dispatch until it is confirmed idle", file=sys.stderr)
        return finish(6, status="prompt_failed", error=str(e), **stop)

    # 5. poll until idle / stall / timeout
    last_change = time.time()
    last_sig = None
    messages: list = []
    outcome = None
    status = "timeout"
    while time.time() - started < args.timeout:
        time.sleep(args.poll_seconds)
        try:
            info = api("GET", f"/api/session/{sid}").get("data", {})
            messages = api("GET", f"/api/session/{sid}/message").get("data", [])
        except Exception:
            info = None  # transient failure: no observable progress this
            # poll. The stall deadline below still applies — a bare
            # `continue` here skipped it, degrading stall recovery to
            # the overall timeout when the service is unreachable
            # (Codex P2 on PR #213).
        if info is not None:
            sig = (info.get("time", {}).get("updated"), len(messages),
                   messages[0].get("id") if messages else None)
            if sig != last_sig:
                last_sig = sig
                last_change = time.time()
            idle_msg = next((m for m in messages
                             if m.get("type") == "idle"
                             and m.get("time", {}).get("created", 0) >= prompt_ms - 5000), None)
            if idle_msg:
                outcome = idle_msg.get("outcome") or info.get("outcome")
                status = "completed"
                break
            if info.get("outcome") and info.get("time", {}).get("idle"):
                outcome = info["outcome"]
                status = "completed"
                break
        if time.time() - last_change > args.stall_seconds:
            status = "stall"
            break

    # 6. on stall/timeout the worker may still be running: interrupt it
    # and confirm idle BEFORE harvesting/returning, so a re-dispatch
    # cannot collide with it in the same worktree.
    stop = {}
    if status in ("stall", "timeout"):
        stop = stop_session(sid)
        if not stop["session_stopped"]:
            stop["session_stop_unconfirmed"] = True
            print(f"WARNING: session {sid} could not be confirmed stopped; "
                  "do NOT re-dispatch until it is confirmed idle", file=sys.stderr)

    # 7. harvest + ledger fields from the session record
    try:
        info = api("GET", f"/api/session/{sid}").get("data", {})
    except Exception:
        info = {}
    hv = harvest(sid, report_path, args.min_report_bytes, messages, pre_dispatch_report)
    extra = {"status": status, "outcome": outcome or info.get("outcome"),
             "tokens": info.get("tokens"), "cost": info.get("cost"), **stop, **hv}
    # The exit decision uses the FINAL outcome (extra["outcome"], from
    # the post-poll fetch): the poll loop can observe the idle marker
    # before the record exposes its outcome, and a session whose final
    # record says failed/interrupted must not exit 0 (Sourcery, PR #213).
    if status == "completed" and extra["outcome"] not in (None, "succeeded"):
        return finish(6, **extra)
    if status == "completed":
        return finish(0 if hv["report_authored"] else 5, **extra)
    if status == "stall":
        return finish(3, **extra)
    return finish(4, **extra)


if __name__ == "__main__":
    sys.exit(main())
