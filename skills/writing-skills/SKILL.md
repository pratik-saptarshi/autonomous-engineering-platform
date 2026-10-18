# Writing Skills

## Know what earns a skill

- Save a reusable method: how to do a kind of task well, the choices that matter, what to check, and how to present the result, so a later conversation with different details can follow it.

- Do not save a task log, one conversation's details, or personal facts. Facts belong in memory and records belong in files or the app that holds them.

- Search first with `muse.skill_search` and read the closest skills. Improve an existing custom skill instead of adding a near-duplicate.

- When the lesson is how to operate one service, write a connector doc instead. To correct a system skill, write an amendment instead of a copy.

## Follow the file layout

- Save each skill as `~/workspace/custom-skills/<skill-name>/SKILL.md` beside its `skill.yaml`. Keep the name in snake_case and distinct from system skill names.

- Write `skill.yaml` with name, title, a one-sentence description, category, and include_in_prompt. Keep include_in_prompt true only for skills that should be visible in every conversation.

- Put long conditional detail in a `references/` folder beside the file and link it. Keep helper scripts the method needs in `scripts/` and call them by full path.

## Write the description for discovery

- Start the description with "Use when" and describe only the triggering conditions: the symptoms, situations, and contexts that signal this skill applies.

- Never summarize the skill's workflow in the description. A description that summarizes the process becomes a shortcut the reader follows instead of reading the skill, and it will skip steps the skill requires.

- Write in third person, keep it concrete and technology-agnostic unless the skill is technology-specific, and cover the keywords someone would search for: error messages, symptoms, synonyms, and tool names.

## Write the body to the standard

- Write to the agent in plain second person and start each instruction with the action.

- Make each instruction a `-` bullet with one blank line between bullets. Keep one idea per bullet in one to three short sentences.

- Use `#` once for the title, `##` for sections, and `###` only for a real subsection.

- Name tools exactly as you call them in backticks, such as `muse.exec` or `subagent.spawn`. Write binaries as full paths under `/opt/hatch/bin`.

- Check every command, flag, field, and URL before you write it, and leave out anything you could not verify.

- Teach the task here and link connector docs for operating a service. Never copy a connector's commands into a skill.

- Say what you verified and what is still untested. Never write secrets into a skill.

## Pressure-test discipline skills

- For skills that enforce a rule, test them the way test-driven-development tests code. Write pressure scenarios first: time pressure, sunk cost, exhaustion, and authority pressure combined.

- Run the scenario with a subagent without the skill and document the exact rationalizations it uses. Those become the rationalization table and red flags in the skill.

- Run the same scenario with the skill and verify the agent now complies. Add explicit counters for every new rationalization until the skill holds under maximum pressure.

- For technique skills, test application on a new scenario. For reference skills, test that the reader can find and correctly apply the information.

## Match the form to the failure

- When the baseline failure is skipping a rule under pressure, use prohibitions plus a rationalization table plus red flags.

- When the failure is wrong-shaped output, use a positive recipe stating what the output is, its parts in order. Prohibition lists backfire here because readers negotiate with don't.

- When the failure is omitting a required element, make it a required structural field in the template they fill in.

- Express real exceptions as their own conditionals on an observable predicate. Never add nuance clauses like unless it matters, which reopen the negotiation.

## Deploy one skill at a time

- Test each skill before deploying it. Never batch multiple untested skills.

- Delete every template comment before saving. Keep the skill under 500 words unless it is a core workflow, and move details to `references/` to stay lean.
