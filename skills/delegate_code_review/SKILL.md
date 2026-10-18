# Delegate Code Review

Run a disciplined diff review where a local CLI handles the deterministic parts (which files to review, which rules apply per file) and you perform the actual review with your own judgment. Adapted from Alibaba OpenCodeReview's delegation mode. No LLM API key is needed: the CLI never calls a model in this mode.

## Determine what to review

- Run `~/workspace/bin/ocr delegate preview --format json` with `muse.exec` in the repository root. It prints the mode (workspace, range, or commit), ref metadata, and the list of reviewable files with insertions and deletions.
- For a branch comparison add `--from <ref> --to <ref>`. For a single commit add `-c <hash>`. To limit scope add `--exclude <patterns>`.
- Build a checklist containing every entry in `reviewable_files`. Every entry must end the run as reviewed or explicitly skipped with a reason. Never silently omit a file.
- For large changesets, work through the checklist in bounded batches grouped by shared rules and diff size. Do not stop after the first high-severity issue.

## Get the rules for each file

- Run `~/workspace/bin/ocr delegate rule --format json <paths>` with `muse.exec`, passing the reviewable file paths. Files sharing the same rule content are grouped together, so pass paths in batches for large changes.
- Treat each rule group as the review checklist for its files. The rules are language-specific and precision-tuned: report only defects likely real in the changed code and its reachable context, since false positives cost reviewer trust.
- Check which rule applies to a single path any time with `~/workspace/bin/ocr rules check <path>`.
- Use `--repo /path` instead of changing directory when the repository is not your working directory.

## Get the diffs

- Choose the diff command from the preview's mode. Use `git --no-pager` for every Git call.
- In range mode run `git --no-pager diff --no-ext-diff --no-textconv --no-color <merge_base>..<to> -- "<path>"`.
- In commit mode run `git --no-pager show --no-ext-diff --no-textconv --no-color <commit> -- "<path>"`.
- In workspace mode run `git --no-pager diff --no-ext-diff --no-textconv --no-color HEAD -- "<path>"` for tracked files, and read untracked files directly with `muse.read` since the entire file is new code.
- For large diffs write the diff to a unique absolute path outside the repository with `--output="<absolute-diff-file>"`, read it in chunks, then delete it. Retry once if Git fails, then record the file as skipped with the error.

## Review and report

- For each reviewable file, read its diff, consult its rule group, and use `muse.read` and codebase search to establish call sites, ownership, and input boundaries before reporting any non-local claim.
- Do not duplicate findings that deterministic tooling (`go vet`, `gofmt`, linters, the compiler) already determines, unless the diff shows a concrete consequence those tools will not express.
- Write each finding with a path, a description of the issue, start and end line numbers in the new file, a category (bug, security, performance, maintainability, test, style, documentation, other), and a severity (critical, high, medium, low).
- Report critical and high findings always. Report medium findings with context. Report low findings only when clearly valuable. Discard likely false positives silently.
- End with a coverage summary: total files, reviewed files, skipped files with reasons, and the coverage rate. Group findings by severity.
