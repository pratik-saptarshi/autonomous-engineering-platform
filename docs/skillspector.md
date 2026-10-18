# SkillSpector — Skill Security Gate

NVIDIA SkillSpector (v2.12.0, Apache-2.0) scans agent skills for security issues before ingestion, installation, or publication. Standing rule: **no skill enters `~/workspace/custom-skills/` without passing the gate.**

## What it checks

71 patterns across 17 categories: prompt injection, anti-refusal, data exfiltration, privilege escalation, supply chain (incl. live OSV.dev CVE lookups), excessive agency, output handling, system-prompt leakage, memory poisoning, tool misuse, rogue agent, trigger abuse, dangerous code (AST), taint tracking, YARA malware signatures, MCP least-privilege, MCP tool poisoning.

Scores 0–100 → SAFE (0–20) / CAUTION (21–50) / DO NOT INSTALL (51+).

## Installation (per machine)

The scanner lives in an isolated venv (not committed — 297MB):

```bash
git clone https://github.com/nvidia/skillspector /tmp/skillinsp
cd /tmp/skillinsp && ~/workspace/skillspector/venv/bin/pip install .  # or fresh venv
```

Expected layout after setup:

```
~/workspace/skillspector/
  venv/                 # isolated Python 3.12 venv (not in git)
  venv/bin/skillspector # CLI
  scan-gate.sh          # pre-ingestion gate wrapper (in git: scripts/)
  USAGE.md              # full usage doc (in git: this file's source)
  baselines/            # per-skill accepted/dismissed findings (in git)
```

## The gate

```bash
scripts/scan-gate.sh /path/to/new-skill/ && cp -r /path/to/new-skill/ ~/workspace/custom-skills/
```

Blocks on score > 50 or any HIGH/CRITICAL finding. Fails closed on scan errors.

## Baselines

`baselines/<skill>.json` records reviewed findings so they don't need re-triage:

```json
{
  "skill": "<name>",
  "accepted": [
    {"pattern": "EA2", "location": "SKILL.md:44",
     "justification": "Why this is intended behavior."}
  ],
  "dismissed": [
    {"pattern": "PE3", "location": "SKILL.md",
     "disposition": "Why this is a false positive."}
  ]
}
```

- **accepted**: true-positive-by-design (e.g. ralph_loop's autonomy).
- **dismissed**: scanner misfired — quote the flagged text, explain the misread.

## Limitations

- Static analysis only (no LLM provider configured). Catches structural issues, not semantic ones like description-behavior mismatches.
- Pattern-based: expect false positives on skills describing powerful operations. Triage, don't blindly obey.

## Baseline established 2026-10-18

All 30 skills scanned: 20 scored 0, highest was 20 (well under the 50 block threshold). 4 accepted baselines, 6 dismissed false positives. One real fix resulted: pinned `rea-agents@6.5.0` in `reverse_engineering` (was `@latest`).
