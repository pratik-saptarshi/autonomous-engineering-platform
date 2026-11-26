#!/usr/bin/env python3
"""Format the sticky Policy Delta PR comment and choose how to upsert it.

Issue #154. The Policy Delta workflow already uploads the report as the
``policy-delta-<head_sha>`` artifact and writes it to the job summary;
this helper turns the same report into ONE sticky PR comment so the
reviewer sees the delta (and the acknowledgement state) without opening
the run. Pure stdlib, no network: the workflow does the API calls.

Bounded claim: the comment is informational. It restates what the
differ computed for one head SHA; the acknowledgement check remains the
gate and a recorded human act, never an approval substitute. A comment
that is stale, truncated or missing changes nothing about the gate.

Comment layout (the first line is the hidden upsert marker)::

    <!-- aep:policy-delta -->
    <!-- aep:policy-delta-fingerprint: <sha256> -->
    ### Policy delta -- `ack-required`
    | head SHA | base SHA | workflow run | outcome |   (as a table)
    <differ report, @-mentions and forged markers neutralised>
    ---
    footer: sticky comment; artifact `policy-delta-<head_sha>`

Outcomes (from the acknowledgement check's exit code): ``ok`` (0:
nothing newly allowed, or acknowledged), ``ack-required`` (1), and
``differ-error`` (2, or anything else -- fail closed).

The whole comment is kept strictly under 65,000 bytes (GitHub rejects
bodies over 65,536 characters): an oversized report is cut on a UTF-8
character boundary, a code fence the cut leaves open is closed, and a
pointer to the artifact is appended.

The fingerprint hashes (head, base, outcome, report text) and NOT the
run URL, so an `edited`-triggered re-run that computes the same thing
yields a ``noop`` plan instead of rewriting the comment.

Usage::

    format_policy_delta_comment.py format --report FILE --head-sha SHA
        --base-sha SHA --run-url URL --ack-rc RC --output FILE
    format_policy_delta_comment.py plan --comments FILE --body-file FILE
        prints ``action=create|update|noop`` [+ ``comment_id=N``]

Exit 0 on success, 2 on bad input.
"""

import argparse
import hashlib
import json
import re
import sys

MARKER = "<!-- aep:policy-delta -->"
FINGERPRINT_PREFIX = "<!-- aep:policy-delta-fingerprint: "
FINGERPRINT_RE = re.compile(
    r"<!-- aep:policy-delta-fingerprint: ([0-9a-f]{64}) -->")
BOT_LOGIN = "github-actions[bot]"
MAX_COMMENT_BYTES = 65000  # the finished comment is strictly smaller
OUTCOMES = ("ok", "ack-required", "differ-error")
_SHA_RE = re.compile(r"^[0-9a-f]{7,64}$")
_ZWSP = "​"


def outcome_from_rc(rc):
    """Map the acknowledgement check's exit code to an outcome. A
    missing or unexpected code means an earlier step failed: fail
    closed to ``differ-error``."""
    return {"0": "ok", "1": "ack-required"}.get(str(rc).strip()
                                                if rc is not None
                                                else "", "differ-error")


def _neutralise(text):
    """Defang report text before it is embedded in a PR comment: a
    skill path such as ``skills/@octocat/x`` must not notify anyone,
    raw HTML tags/comments (including forged markers and ``-->``) must
    not render, and markdown links must not inject phishing targets."""
    text = text.replace("@", "@" + _ZWSP)
    text = re.sub(r"<(?=[A-Za-z/!?])", "&lt;", text)
    text = text.replace("-->", "--&gt;")
    text = re.sub(r"\[([^\]]*)\]\(", r"\\[\1\\](", text)
    return text


def _cut_utf8(text, limit):
    """text truncated to at most `limit` bytes of UTF-8, on a
    character boundary and preferably at a line end."""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    cut = raw[:limit].decode("utf-8", errors="ignore")
    nl = cut.rfind("\n")
    if nl > limit // 2:
        cut = cut[:nl]
    return cut


def _close_open_fence(text):
    open_char, open_len = None, 0
    for ln in text.splitlines():
        m = re.match(r"^\s*(`{3,}|~{3,})", ln)
        if not m:
            continue
        token = m.group(1)
        ch, n = token[0], len(token)
        if open_char is None:
            open_char, open_len = ch, n
        elif ch == open_char and n >= open_len \
                and not ln[m.end():].strip():
            open_char, open_len = None, 0
    return text + (f"\n{open_char * open_len}" if open_char else "")


def _validate(head_sha, base_sha, run_url, outcome):
    if not _SHA_RE.match(head_sha or ""):
        raise ValueError(f"head SHA is not a hex SHA: {head_sha!r}")
    if not _SHA_RE.match(base_sha or ""):
        raise ValueError(f"base SHA is not a hex SHA: {base_sha!r}")
    if not re.match(r"^https://[^\s<>()\[\]]+$", run_url or ""):
        raise ValueError(f"run URL is not an https URL: {run_url!r}")
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}: {outcome!r}")


def fingerprint(head_sha, base_sha, outcome, report):
    """Content identity of a comment: everything except the run URL."""
    blob = json.dumps([head_sha, base_sha, outcome, report],
                      ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def format_comment(report, head_sha, base_sha, run_url, outcome,
                   max_bytes=MAX_COMMENT_BYTES):
    """The sticky comment body: marker, fingerprint, metadata header
    (head SHA, base SHA, run URL, outcome), the report, and a footer
    naming the artifact. Strictly under `max_bytes`."""
    _validate(head_sha, base_sha, run_url, outcome)
    report = _neutralise(report or "")
    artifact = f"policy-delta-{head_sha}"

    def compose(body, truncated):
        parts = [
            MARKER,
            f"{FINGERPRINT_PREFIX}"
            f"{fingerprint(head_sha, base_sha, outcome, body)} -->",
            f"### Policy delta — `{outcome}`",
            "",
            "| | |",
            "|---|---|",
            f"| Outcome | `{outcome}` |",
            f"| Head SHA | `{head_sha}` |",
            f"| Base SHA | `{base_sha}` |",
            f"| Workflow run | {run_url} |",
            "",
            body.rstrip("\n"),
            "",
        ]
        if truncated:
            parts += [
                f"> **Report truncated** to fit the PR comment size "
                f"limit. The full report is in the `{artifact}` "
                f"artifact and the job summary of the [workflow run]"
                f"({run_url}).", ""]
        parts += [
            "---",
            f"_Sticky comment maintained by the Policy Delta workflow "
            f"for head `{head_sha[:12]}`; the full report is the "
            f"`{artifact}` artifact. Informational only: the "
            f"acknowledgement check is the gate._",
        ]
        return "\n".join(parts) + "\n"

    full = compose(report, False)
    if len(full.encode("utf-8")) < max_bytes:
        return full
    # Binary-shrink the report until the whole comment fits.
    overhead = len(compose("", True).encode("utf-8"))
    budget = max(0, max_bytes - overhead - 16)
    while True:
        body = _close_open_fence(_cut_utf8(report, budget))
        out = compose(body, True)
        if len(out.encode("utf-8")) < max_bytes or budget == 0:
            return out
        budget = max(0, budget - max(16, budget // 50))


def parse_comments(comments):
    """A list of comment dicts from a list, JSON text, or the
    back-to-back JSON arrays `gh api --paginate` prints."""
    if isinstance(comments, list):
        return comments
    out, text, pos = [], (comments or "").strip(), 0
    dec = json.JSONDecoder()
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        value, pos = dec.raw_decode(text, pos)
        if isinstance(value, list):
            out.extend(value)
        elif isinstance(value, dict):
            out.append(value)
    return out


def select_upsert_target(comments):
    """The id of the existing sticky comment to PATCH, or None (POST a
    new one): the lowest-id comment authored by ``github-actions[bot]``
    whose body contains the hidden marker. Comments by anyone else are
    ignored even if they carry the marker."""
    best = None
    for c in parse_comments(comments):
        if not isinstance(c, dict):
            continue
        user = c.get("user")
        body = c.get("body")
        cid = c.get("id")
        if not isinstance(user, dict) or user.get("login") != BOT_LOGIN \
                or user.get("type") != "Bot":
            continue
        if not isinstance(body, str) or not body.lstrip().startswith(MARKER):
            continue
        if not isinstance(cid, int) or isinstance(cid, bool):
            continue
        if best is None or cid < best:
            best = cid
    return best


def plan_upsert(comments, new_body):
    """(action, comment_id): ``create`` (no sticky comment yet),
    ``update`` (the stored content differs), or ``noop`` (the stored
    fingerprint equals the new one -- no churn on a re-run that
    computed the same thing)."""
    parsed = parse_comments(comments)
    target = select_upsert_target(parsed)
    if target is None:
        return ("create", None)
    new_fp = FINGERPRINT_RE.search(new_body)
    for c in parsed:
        if isinstance(c, dict) and c.get("id") == target:
            old_fp = FINGERPRINT_RE.search(c.get("body") or "")
            if old_fp and new_fp and old_fp.group(1) == new_fp.group(1):
                return ("noop", target)
    return ("update", target)


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("format")
    f.add_argument("--report", required=True)
    f.add_argument("--head-sha", required=True)
    f.add_argument("--base-sha", required=True)
    f.add_argument("--run-url", required=True)
    f.add_argument("--ack-rc", default="")
    f.add_argument("--output", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--comments", required=True)
    p.add_argument("--body-file", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "format":
            outcome = outcome_from_rc(args.ack_rc)
            try:
                report = _read(args.report)
            except OSError:
                report = ("The policy delta report was not produced by "
                          "an earlier step (the report was not produced; "
                          "the acknowledgement check fails closed).\n")
                outcome = "differ-error"
            body = format_comment(report, args.head_sha, args.base_sha,
                                  args.run_url, outcome)
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(body)
        else:
            action, cid = plan_upsert(_read(args.comments),
                                      _read(args.body_file))
            print(f"action={action}")
            if cid is not None:
                print(f"comment_id={int(cid)}")
    except (ValueError, OSError) as e:
        print(f"format_policy_delta_comment: error: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
