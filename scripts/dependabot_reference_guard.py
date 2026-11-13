#!/usr/bin/env python3
"""Dependabot reference guard — routes bot PRs that touch reference/**.

Bounded claim: this script decides, from a PR's author and changed-file
list alone, whether the PR is a Dependabot-authored change to a vendored
snapshot tree. For exactly those PRs it emits (dry-run) or performs
(--apply) three actions: label ``vendor-refresh-needed``, post a comment
naming the re-vendor lane as the route, and close the PR.

Why: everything under ``reference/`` is a byte-pinned snapshot (see
``.github/vendor-*.sha256`` and each tree's PROVENANCE.md) that changes
only by wholesale re-vendoring. ``.github/dependabot.yml`` scopes
*version* updates away from ``reference/`` by omission, but *security*
updates are governed by the repo Settings toggle, not that file, and
they do propose in-place edits inside vendored trees — edits that can
never merge (vendor-integrity fails by construction, and a merged bump
would falsify the pinned provenance). Closing is the recurrence
control: Dependabot does not re-raise a closed update for the same
version, so a closed bot PR stays closed until a human re-vendors.

The companion workflow runs on ``pull_request_target`` because
Dependabot-triggered ``pull_request`` workflows receive a read-only
token that cannot label, comment, or close. The script only ever reads
PR metadata; no PR code is checked out or executed.

Usage:

    dependabot_reference_guard.py --pr N --author LOGIN --files LIST
    dependabot_reference_guard.py --pr N --author LOGIN --files LIST --apply

``--files`` names a text file with one changed path per line. Without
``--apply`` the action plan is printed as JSON and nothing is executed.
"""

import argparse
import json
import subprocess
import sys

LABEL = "vendor-refresh-needed"
BOT_AUTHORS = {"dependabot[bot]", "dependabot"}
REFERENCE_PREFIX = "reference/"

COMMENT_BODY = """\
This PR was opened by Dependabot and changes files under `reference/**`.

Everything under `reference/` is a byte-pinned vendored snapshot: it
changes only by wholesale re-vendoring (replace the tree with a new
pinned snapshot and regenerate its `.github/vendor-*.sha256` manifest
in the same change), never by in-place dependency edits. An in-place
bump cannot merge — the vendor-integrity check fails by construction,
and merging it would leave the tree matching no upstream commit.

Closing this PR and labelling it `vendor-refresh-needed` so the update
is picked up by the re-vendor lane. Dependabot does not re-raise a
closed update for the same version, so this stays closed until a human
re-vendors the tree at a pin that carries the fix.

— dependabot-reference-guard (automation; template by Musebot-Astro)"""


def decide(author, files):
    """Return the action plan for a PR: [] unless it is a bot PR that
    touches a vendored snapshot tree."""
    if author not in BOT_AUTHORS:
        return []
    if not any(path.startswith(REFERENCE_PREFIX) for path in files):
        return []
    return [
        {"action": "label", "label": LABEL},
        {"action": "comment", "body": COMMENT_BODY},
        {"action": "close"},
    ]


def apply_actions(pr, actions):
    for action in actions:
        kind = action["action"]
        if kind == "label":
            cmd = ["gh", "pr", "edit", str(pr), "--add-label", action["label"]]
        elif kind == "comment":
            cmd = ["gh", "pr", "comment", str(pr), "--body", action["body"]]
        elif kind == "close":
            cmd = ["gh", "pr", "close", str(pr)]
        else:  # pragma: no cover - decide() never emits other kinds
            raise ValueError(f"unknown action: {kind}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(
                f"error: {' '.join(cmd[:3])} failed: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return result.returncode
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument(
        "--files",
        required=True,
        help="path to a text file with one changed path per line",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the actions via gh (default: print the plan as JSON)",
    )
    args = parser.parse_args(argv)

    with open(args.files, encoding="utf-8") as fh:
        files = [line.strip() for line in fh if line.strip()]

    actions = decide(args.author, files)
    if not args.apply:
        print(json.dumps({"pr": args.pr, "actions": actions}, indent=2))
        return 0
    return apply_actions(args.pr, actions)


if __name__ == "__main__":
    raise SystemExit(main())
