# Reverse Engineering

Adapted from REA (Reverse Engineer Anything). Use this when a claim depends on a shipped binary or package, on decompilation, or on runtime evidence rather than source you can read. For ordinary analysis of a source repository you can read, use the code_explorer or research skill instead and skip this one.

## Use what is available here

- The working tool is the REA CLI via `npx -y rea-agents@6.5.0` (verified: version 6.5.0 prints, and JavaScript application analysis returns a structured Evidence record). It needs no installation and writes only to the npm cache. The version is pinned — do not use `@latest` (supply-chain hygiene).
- There is no MCP client in this environment, so the REA MCP server cannot be registered here. Hopper and IDA are not installed (Hopper needs a paid license).
- Ghidra 12.1.4 IS installed (2026-10-20): `GHIDRA_INSTALL_DIR=~/opt/ghidra_12.1.4_PUBLIC`, Temurin JDK 25 at `~/opt/jdk-25.0.4.1+1` (`JAVA_HOME`; both exported in `~/.bashrc`, `support/` on PATH). Native deep analysis runs headless via `analyzeHeadless` (verified: boots and prints usage) — no display needed. Keep memory modest: this VM has 7GB RAM with ~6GB typically in use, so cap the heap (e.g. 2G) and prefer bounded `-analysisTimeoutPerFile`.
- Static JavaScript and Electron application analysis works through the REA CLI with no engine.
- Analyze a JavaScript application or Electron tree with:

  `npx -y rea-agents@6.5.0 analyze-javascript-application /absolute/path/to/app --json`

- Read the returned Evidence record the way you would read a lab report: identity and SHA-256 digests, the graph of modules, stated limitations, and unknowns. Do not treat a truncated preview as the complete record.

## Route the target first

- Identify the artifact before analyzing: an ASAR or extracted JavaScript tree goes to JavaScript application analysis, an archive or installer goes to inventory first, a firmware image goes to firmware inspection only if the required extractor is present.
- If the user says only "my app" without a name or path, ask which app before searching. Never pick an example target on the user's behalf.
- For a target the available tooling cannot handle here (for example Hopper/IDA-specific workflows), say so plainly and do the useful supported part instead of faking the rest. Native disassembly and decompilation go through Ghidra headless.

## Invoke Ghidra only when needed

Ghidra headless is the heaviest tool here (JVM on a 7GB VM). Route cheapest-first and start
it only when the evidence requires it:

- If the question is answerable from metadata, `strings`, or the REA CLI evidence record
  (JS/Electron trees, archive inventory), do that and stop. Do not start Ghidra.
- Invoke Ghidra headless only when ALL hold: the target is a native binary (ELF/Mach-O/PE,
  or firmware with its extractor present) AND the question needs disassembly,
  decompilation, CFG, or cross-references AND cheaper triage left a concrete gap.
- Never invoke Ghidra when the question is already answered by cheaper evidence, when an
  identical analysis already ran without a changed input or resolved blocker, or when the
  target is a source tree you can read (use code_explorer instead).
- When invoking: cap the heap (~2G), set a bounded `-analysisTimeoutPerFile`, and prefer
  `-noanalysis` plus targeted scripts for triage before full auto-analysis.
- Record the routing decision (tool chosen and why) in the finding ledger so repeats
  are visible and auditable.

## Work summary-first and keep evidence honest

- Start with the smallest useful overview, then drill into the specific question. For a large or unknown-size target, request the summary view first and page into modules only where the question leads.
- Every conclusion must distinguish observations from inferences from unknowns. Cite evidence IDs. Preserve the tool's stated limitations and incomplete coverage.
- Never imply that static analysis observed execution. Static findings describe structure; only runtime observation describes behavior.
- Do not repeat an identical analysis without a changed input or a resolved blocker.

## Run a staged investigation

- Turn a broad request into a checklist of questions, each paired with the evidence its answer needs. Resolve the target's identity from the conversation before asking for information again.
- Follow each question from its entry point through data and state changes to its result. Batch related operations around one hypothesis, then expand only when the evidence leaves a concrete gap.
- Keep a concise finding ledger linking each conclusion to evidence IDs, the search boundary, and remaining unknowns, so later passes reuse results instead of repeating work.
- Before finishing, revisit the checklist. Mark each question answered, partially answered, or unresolved based on its evidence. Do not describe an investigation as complete while required questions remain open.

## Finish the task

- Explain findings in plain language tied to the evidence. When the user asks to build something from what you learned, use normal coding tools and keep observed behavior separate from your own design choices.
