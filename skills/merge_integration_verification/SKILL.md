# Merge Integration Verification

## Census conflicts by class before resolving anything

- Classify every conflicted path before resolving any of them, so the resolution strategy is chosen per class rather than improvised per file.

- Class A: one side is byte-identical to the ancestor or pin, so take the other side wholesale; blob-verify the count of Class A paths instead of trusting the headline census number, because the fork-main census headline said 46 Class A paths while the file it listed contained 42.

- Class B: both sides genuinely changed, so resolve per file by merging the intent of each side rather than taking either side whole.

- Class C: the conflict is about file location or rename, so keep the ruled literal paths rather than whichever path a side preferred.

- Treat any both-sides-changed file whose resolution would change adjudicated semantics, and which lacks precedent, as a STOP file: leave it unresolved, group it into owner rulings, and do not commit the merge past it.

## Present STOP files as grouped rulings

- Present STOP files as a small number of grouped rulings rather than a file-by-file list, each ruling carrying a recommendation and its honest caveats.

- Mark which recommendations rest on preparation judgment and which are lane-verified, so the owner can weigh each recommendation by the evidence behind it.

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

## Prove adjudicated files by function inventory

- After adjudication, inventory the functions of each adjudicated file before and after, and require the counts to match exactly, with zero functions lost and zero duplicated (precedent: the Direction A adjudication closed daemon.rs at 140/140, ingest.rs at 168/168 and server.rs at 232/232).

- Compile the tree after the inventory, because compiling catches splice damage in files already marked resolved that an inventory alone can miss.

- Repair any splice damage the compile finds in already-resolved files and disclose the repair, rather than folding it silently into the resolution (precedent: compiling caught and repaired 9 class-(c) splice damages in the Direction A adjudication).

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

## Census a moved upstream pin before re-pinning

- When the upstream pin moves under a composed or adjudicated tree, census the delta from pin to pin before touching the tree: the commits, the files, and every hit on the composed or protected surface.

- Run a trial merge against the new pin and count its conflicts, then rule RE-PIN REQUIRED or land-as-is on that evidence before asking for any push approval (precedent: the B8 census at pin 216e9d56 counted 44 trial-merge conflicts and ruled RE-PIN REQUIRED).

## Repair blocking compile errors as Cluster 0

- If the merge or re-pin introduces compile errors that block every test suite, that repair is Cluster 0 and runs ahead of every substantive cluster, and the new-head baseline is established from it (precedent: upstream mesh tests written against sync APIs auto-merged onto the async substrate produced 4 E0599 errors, in test code only, and repairing them first unblocked every suite).

## Disposition every prior blocker at the new head

- After a re-pin, disposition every prior blocker individually at the new head as PERSISTS, PERSISTS ALTERED, DISCHARGED BY ABSORPTION or DISCHARGED IN SUBSTANCE, each with evidence at the moved site.

- A blocker is DISCHARGED BY ABSORPTION only when the absorbing fix is verified in-tree; on restart it is verification-only, so run the ruling's regression test rather than re-implementing the fix.

- Treat a new finding on the absorbing fix's own code as a new intake item, not as a reopening of the discharged blocker.

## Hold protected files and re-prove judged fixes

- Hold files under adjudication to exactly their adjudicated state plus the upstream delta, and record any held-back set by explicit file list (precedent: plugins held back as a recorded 34-file list during the re-pin).

- Re-prove every previously judged fix on the new tree by executing its targeted tests, never by assuming it carried (precedent: the re-pin re-proved B1 2/2, B2 3/3, B9 3/3, B4 1/1, C1/C2 2/2 and Cluster 0 2/2, and DR-2 stayed byte-identical despite a 597-line upstream delta).

## Diagnose squash-replay conflict explosions

- If a sync merge explodes into conflicts on content the fork already holds, diagnose a dishonest merge-base caused by prior squash-merged syncs: the merge-base predates the last synced upstream state, so git replays changes the fork already holds as if they were new.

- Prove the replayed paths byte-identical to the last synced state before treating the explosion as replay rather than real divergence.

- Recommend landing future syncs as true merge commits, so the merge-base stays honest and the next sync does not replay.

## Available connectors

- [GitHub](/opt/hatch/connectors/github/CONNECTOR.md) for reading the merge pull request, its base and head commits and its check runs when the merge landed through a pull request.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Run an independent reviewer or panel over the tree wide results when the merge is large, and give that reviewer the parent comparison output rather than the merge summary.

- Reproduce a suspected inherited failure on a clean parent checkout before classifying it, so an environment artifact and a real inherited defect are not confused.

- Park genuinely undecidable semantic conflicts with a written citation and a disabled or ignored marker instead of forcing a resolution the evidence cannot support.
