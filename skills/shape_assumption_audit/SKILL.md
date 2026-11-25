# Shape Assumption Audit

## Enumerate the shape assumptions

- List every shape the existing tests and fixtures quietly assume before you judge the code ready, writing one line per assumption in the review ledger.

- Check the graph shape first and ask whether every fixture is a linear chain where a prefix, a causal closure and a reachable set happen to coincide.

- Check the timing shape and ask whether every run is quiescent, with no write, append or collection step interleaved with another operation.

- Check the handle shape and ask whether every test opens the store or resource once, through one handle, on an already initialized target.

- Check the input shape and ask whether every record the write path accepts was produced by the system itself, fully decodable and free of duplicate or tampered fields — and whether every field read back from the system's own durable records that steers an effect is re-validated against an anchor independent of that record, since a record never vouches for its own scope.

- Check the path shape and ask whether every target is a plain directory or file of the expected kind, with no symlink, file in place of a directory or empty target standing in for a real one.

- Check the self-inflicted shape and ask what shapes the operation itself creates between its own steps — an ancestor it replaces, a link it restores, a write it lands — and whether any later step resolves a path through the operation's own product.

- Check the second-execution shape and ask what state a first execution that died mid-sequence leaves behind, and whether a repeated run, a recovery pass, or a different verb meeting that debris can still complete or correctly refuse.

- Ask, under the timing shape, between which two adjacent statements the process can die and what the durable record claims at that exact point — a window invisible at operation granularity is often obvious at statement granularity.

## Build one breaking fixture per assumption

- Build one fixture that breaks each listed assumption, such as a forked or branching graph where a published prefix and its causal closure differ.

- Add a concurrent fixture that interleaves the operation under review with a competing write, and run it under the race detector where the toolchain offers one.

- Add a first use fixture that opens an empty or uninitialized target and a second fixture that opens the same target through two handles at once.

- Add a hostile input fixture that feeds the write path an undecodable record, a duplicate key and a record whose stored metadata disagrees with the data it describes, and confirm the write is rejected rather than stored.

- Add a path fixture that points the operation at a symlinked root, a file where a directory is expected and an empty path, and confirm the failure is a clear local error rather than a raw tool error.

- Add a self-replacement fixture that makes the operation replace an ancestor (above all with a symlink) and then touch a descendant, and confirm nothing outside the target tree changes.

- Add a second-execution fixture that kills the operation at a step prefix — including inside its own recovery path — then re-enters through the same verb, a repeated recovery, and a different verb, and pin each re-entry's outcome.

- Keep each fixture minimal and named for the assumption it breaks, so a failure points at the assumption and not at a large scenario.

## Reproduce before fixing, then re-audit the class

- Reproduce every suspected defect against the current head before you dispatch a fix, and record the failing fixture and its output in the ledger.

- Fix the mechanism behind a reproduced defect rather than the single fixture, then rerun the whole shape fixture set instead of only the one that failed.

- Treat a second defect in the same shape class as a census trigger and enumerate every operation that shares that assumption before you fix further instances one by one.

- Deliver a class census as a machine-checked artifact (an audit test or gate check that re-enumerates the sites on every run) whenever the codebase offers that idiom; a hand-written census is a draft with an expiry, and its counts come from the machine enumeration, never from a hand-written summary.

- Re-check any claim that a review round is closed against the live review threads at report time, because a reviewer can open new threads after an earlier round was reported clean.

## Report the audit

- Report the assumptions found, the fixture built for each one, which fixtures failed on the pre fix head and which pass on the final head.

- Name any assumption you could not build a fixture for as untested, with the reason, rather than folding it into a general pass.

- State the gate result only from the final head, with the race run and the full fixture set both tied to that head.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reading pull request diffs, review threads and check results on the branch under audit.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Run the audit as an independent panel through the roundtable review skill when the system is safety or money bearing, because the panel that found these defects was external to the layers that missed them.

- Shrink the audit to the two or three assumptions a small change actually touches when the diff is narrow, and grow it to the full list when the change adds a storage, collection or concurrency mechanism.
