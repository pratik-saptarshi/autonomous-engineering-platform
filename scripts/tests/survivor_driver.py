#!/usr/bin/env python3
"""Subprocess harness for the Task 2 survivor-reap tests.

Runs the verifier (via mechanical_verify.main) inside THIS process so
the PR_SET_CHILD_SUBREAPER flag main() sets — and the orphaned
descendants that reparent here — never touch the test-runner process.

Before invoking the verifier the driver spawns its OWN long-lived
bystander helper (a direct child of this process). The helper predates
the verifier's pre-spawn snapshot, so the survivor sweep must never
signal it; the driver records whether it survived in the helper status
file.

The fixture root is a Makefile project whose test recipe runs a
spawner that launches a `setsid` writer (which appends to a marker
file for up to 120 s) and then, in "timeout" mode, sleeps so the
verifier's timeout path is exercised. The marker, pid files, and
receipts all live OUTSIDE the fixture root so the run's tree binding
is not disturbed by the writer's appends.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mechanical_verify

SPAWNER_SRC = '''\
import subprocess
import sys
import time
from pathlib import Path

WRITER_SRC = (
    "import sys, time\\n"
    "from pathlib import Path\\n"
    "marker = Path(sys.argv[1])\\n"
    "end = time.monotonic() + 120\\n"
    "while time.monotonic() < end:\\n"
    "    with marker.open('a') as fh:\\n"
    "        fh.write('x')\\n"
    "    time.sleep(0.05)\\n"
)


def main() -> None:
    marker, pid_file, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    writer = subprocess.Popen(
        [sys.executable, "-c", WRITER_SRC, marker],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(pid_file).write_text(str(writer.pid))
    if mode == "timeout":
        time.sleep(120)


if __name__ == "__main__":
    main()
'''

MAKEFILE = 'test:\n\t@python3 spawner.py "$(MARKER)" "$(PIDFILE)" "$(MODE)"\n'


def main() -> int:
    parser = argparse.ArgumentParser(prog="survivor_driver.py")
    parser.add_argument("--root", required=True)
    parser.add_argument("--mode", choices=("success", "timeout"), required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--writer-pid-file", required=True)
    parser.add_argument("--receipts", required=True)
    parser.add_argument("--helper-pid-file", required=True)
    parser.add_argument("--helper-status-file", required=True)
    parser.add_argument("--rc-file", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text(MAKEFILE)
    (root / "spawner.py").write_text(SPAWNER_SRC)

    # Bystander: spawned BEFORE the verifier runs and a direct child
    # of this process, so it is inside the pre-spawn snapshot the
    # sweep takes — it must come through the run unharmed.
    helper = subprocess.Popen(["sleep", "120"])
    Path(args.helper_pid_file).write_text(str(helper.pid))

    os.environ["MARKER"] = args.marker
    os.environ["PIDFILE"] = args.writer_pid_file
    os.environ["MODE"] = args.mode
    try:
        rc = mechanical_verify.main(
            [
                "verify",
                "--root",
                str(root),
                "--task",
                "survivor",
                "--receipts",
                args.receipts,
                "--timeout",
                str(args.timeout),
            ]
        )
    finally:
        alive = helper.poll() is None
        Path(args.helper_status_file).write_text("alive" if alive else "dead")
        if alive:
            helper.kill()
            helper.wait()
    Path(args.rc_file).write_text(str(rc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
