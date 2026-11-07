# GitHub issues

Use `gh` when it is installed and authenticated; it handles auth, rate
limits, and JSON. Fall back to the public API with curl, then to a URL
your partner opens.

## Search

```bash
gh search issues --repo obra/superpowers --limit 10 "<terms>" \
  --json number,state,title --jq '.[] | "\(.number)\t\(.state)\t\(.title)"'
```

Without `gh` (unauthenticated, 10 requests a minute):

```bash
curl -s -H "Accept: application/vnd.github+json" \
  "https://api.github.com/search/issues?q=repo:obra/superpowers+is:issue+<url-encoded terms>&per_page=10" \
  | jq -r '.items[] | "\(.number)\t\(.state)\t\(.title)"'
```

Without curl, hand over `https://github.com/obra/superpowers/issues?q=<terms>`.

## File

Every posting from this step consumes the one gated artifact from
SKILL.md step 5: `<case-workspace>/issue-gate/post-body.md` — the filled
text after the issue-body scrub gate's audit has returned CLEAN. Never
post the filled template, the filled report, or
`issue-gate/draft-body.md` directly.

Write the filled `templates/issue.md` to the workspace, run it through
the gate, and show your partner the exact text of `post-body.md`. After
approval:

```bash
gh issue create --repo obra/superpowers --title "<title>" \
  --body-file <case-workspace>/issue-gate/post-body.md \
  --label bug --label automated-issue-report
```

GitHub drops labels silently when the reporter lacks push access, so the
labels land only for collaborators; the template footer still marks the
issue as skill-filed. `gh` cannot attach files: give your partner the
bundle path to attach through the browser after the issue exists.

Adding the report to an existing issue (a comment) goes through the same
gate: copy the filled report text into the gate as its `draft-body.md`,
and post only the resulting `post-body.md` contents, after your partner
approves that exact text:

```bash
gh issue comment <number> --repo obra/superpowers \
  --body-file <case-workspace>/issue-gate/post-body.md
```

Without `gh`, hand over a prefilled link on the `diagnosis_report.md`
template, which applies both labels for any reporter. The link's body is
the url-encoded content of `issue-gate/post-body.md` — never the
unscrubbed draft:

```
https://github.com/obra/superpowers/issues/new?template=diagnosis_report.md&title=<url-encoded title>&body=<url-encoded content of issue-gate/post-body.md>
```

GitHub rejects URLs over about 8,000 characters; past that, send the link
with the title only and tell your partner to paste the body from
`issue-gate/post-body.md`.
