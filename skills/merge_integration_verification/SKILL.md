# Merge Integration Verification

## Enumerate the whole tree by file type

- Enumerate candidate files by file type across the whole tree after a merge of diverged branches, never by a directory list and never by the changed files alone.

- Parse every structured file the tree contains, including JSON, YAML and TOML, and treat a parse failure in any file as a merge defect until it is traced to a parent.

- Check YAML and other keyed formats for duplicate top level keys, because a duplicated key silently shadows one parent version of a job, setting or section.

- Include embedded files in scope wherever they live, such as files pulled in by include macros, code generation or packaging steps, even when they sit outside the source directories the build compiles.

## Compare the result against both parents

- Compare each suspect file against both parent versions and classify it as matching one parent, matching a deliberate resolution, or matching neither parent.

- Sweep for concatenation damage by testing whether any file equals one parent version followed by the other parent version, in either order.

- Sweep for shadowing damage by looking for duplicated definitions, duplicated data definitions and duplicated registrations that presence checks read as normal.

- Inventory tests and other annotated items by their annotation or attribute, not by name alone, because a splice can keep the item name while dropping the attribute that makes it run.

## Execute rather than inspect presence

- Run the full test suite and the relevant builds, because presence, marker and build only checks cannot see reachability or runtime damage.

- Read the runner stderr and its caused by chain alongside the test verdicts, and record signal codes, so an abort that kills the runner mid suite is not reported as an ordinary failure list.

- Count how many tests actually executed against the inventory, and name any tests that never ran because the runner died or a job was shadowed.

- Census error handling call sites touched by the merge for branches that convert an error such as a busy or locked store into an empty or clean looking success, and classify each one as fixed or deliberately left.

## Classify before claiming acceptance

- Classify every failure as a merge loss, an inherited parent failure or an environment artifact, and cite the parent run or the local reproduction behind each classification.

- State the exact scope every gate covered, and never phrase an acceptance claim more broadly than the gates that ran, so a suite scoped claim is not reported as a tree wide one.

- Fix a gate scope failure by widening the gate to the whole tree by file type, not by adding the one directory that just escaped to the old list.

- Report the merge as verified only when the tree wide parses, the parent comparisons, the execution counts and the failure classifications all agree.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reading the merge pull request, its base and head commits and its check runs when the merge landed through a pull request.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Run an independent reviewer or panel over the tree wide results when the merge is large, and give that reviewer the parent comparison output rather than the merge summary.

- Reproduce a suspected inherited failure on a clean parent checkout before classifying it, so an environment artifact and a real inherited defect are not confused.

- Park genuinely undecidable semantic conflicts with a written citation and a disabled or ignored marker instead of forcing a resolution the evidence cannot support.
