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
    3  stall declared (bounded waits, no progress) — partial harvested
    4  overall timeout — partial harvested
    5  session completed but report missing/trivial (harvested fallback
       written); controller must treat the task as UNREPORTED
    6  session ended with outcome=failed/interrupted
    64 usage / input error
"""

import argparse
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
    status = g("status", "--porcelain") or ""
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


def harvest(session_id: str, report_path: Path, min_bytes: int,
            messages: list) -> dict:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists() and report_path.stat().st_size >= min_bytes:
        return {"report": str(report_path), "report_bytes": report_path.stat().st_size,
                "report_authored": True}
    text = final_assistant_text(messages)
    marker = ("<!-- HARVESTED-NOT-AUTHORED: the session ended without writing "
              "its report file. The text below is the final assistant message "
              "extracted by dispatch.py. The controller must treat this task "
              "as UNREPORTED. -->\n\n")
    report_path.write_text(marker + (text or "(no assistant text found in transcript)") + "\n")
    return {"report": str(report_path), "report_bytes": report_path.stat().st_size,
            "report_authored": False}


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

    OPENCODE = find_opencode()
    started = time.time()
    ledger_rec = {
        "ts_start": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "title": args.title, "model": args.model, "agent": args.agent,
        "workdir": str(workdir), "brief": str(brief_path),
        "report": str(report_path), "git_before": git_snapshot(workdir),
    }

    def finish(code: int, **extra):
        ledger_rec.update(extra)
        ledger_rec["wall_seconds"] = round(time.time() - started, 1)
        ledger_rec["git_after"] = git_snapshot(workdir)
        Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
        with open(args.ledger, "a") as f:
            f.write(json.dumps(ledger_rec) + "\n")
        print(json.dumps(ledger_rec, indent=1))
        return code

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
    archive = Path(args.archive_brief).expanduser().resolve() if args.archive_brief \
        else report_path.with_suffix(report_path.suffix + ".brief.md")
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(brief_text)
    ledger_rec["brief_archived"] = str(archive)

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

    # 4. prompt
    prompt_ms = int(time.time() * 1000)
    try:
        api("POST", f"/api/session/{sid}/prompt", {"text": brief_text}, timeout=180)
    except Exception as e:
        return finish(6, status="prompt_failed", error=str(e))

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
            continue  # transient; the stall/timeout budgets still apply
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

    # 6. harvest + ledger fields from the session record
    try:
        info = api("GET", f"/api/session/{sid}").get("data", {})
    except Exception:
        info = {}
    hv = harvest(sid, report_path, args.min_report_bytes, messages)
    extra = {"status": status, "outcome": outcome or info.get("outcome"),
             "tokens": info.get("tokens"), "cost": info.get("cost"), **hv}
    if status == "completed" and outcome not in (None, "succeeded"):
        return finish(6, **extra)
    if status == "completed":
        return finish(0 if hv["report_authored"] else 5, **extra)
    if status == "stall":
        return finish(3, **extra)
    return finish(4, **extra)


if __name__ == "__main__":
    sys.exit(main())
