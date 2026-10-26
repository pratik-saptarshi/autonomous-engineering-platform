# Model switch plan: NomicEmbedTextV15 (768d) → BGESmallENV15Q (384d)

Prepared 2026-10-23. Status: **EXECUTED 2026-10-23 22:28–22:40 CDT** on Pratik's
explicit go-ahead, with his added constraint that no memories/data be lost.

## Execution record (2026-10-23)

- Preservation before any change (artifacts in `model-switch-20261023/`):
  `backup-pre-switch/` snapshot (restore-rehearsed: doctor on the restored copy
  showed dap 82 / global 5 / guard 3), `db-raw-copy/` (sha256 identical to the
  live db file), `export-full.json` + `export-with-archived.json` (90 nodes).
- Carry-over decision: **everything carried, nothing dropped** — all 90
  memories including the 82 `dap` tasks (their keep/drop question stays open;
  a fresh store made it settle-able later instead of by omission).
- Mechanism executed: daemon stopped → old store renamed to
  `~/.config/NeuroStrata/data/db-nomic768-2026-10-23/` (intact, untouched) →
  embedders.json reordered so BGESmallENV15Q is the default (covers watchdog,
  MCP stdio spawn, and CLI; prior file kept as
  `embedders.json.bak-preswitch-20261023`) → daemon booted once to create the
  fresh 384-dim store → re-populated via `model-switch-20261023/repopulate.py`
  (add + set-metadata, 148 `blocked_by` references remapped old→new ID;
  `id-map.json` holds the full mapping).
- Verification: export-vs-export reconciliation **90/90 exact** (namespace,
  type, content, location, metadata after ID remap); doctor counts match;
  `task validate` reads the dap tasks live; recall — all 4 baseline queries
  return the same memories as top hits (files `recall-baseline-nomic.txt`,
  `recall-after-q.txt`). Note: `dap` semantic search returned no results under
  BOTH models (tasks live in the task subsystem, not search), so dap was
  verified by reconciliation + task validate instead.
- Result: live daemon RSS **885 MB (Nomic) → 145 MB (BGESmallENV15Q)**.
- Rollback unchanged (below). The old store stays as `db-nomic768-2026-10-23/`
  until Pratik directs otherwise under the deletion rule.

## Why

The local embedder's weights dominate daemon memory. Measured on this VM
(one-shot `add` process peak RSS, same code path, 2026-10-23):

- NomicEmbedTextV15: **881 MB** peak (model file 547 MB on disk)
- BGESmallENV15Q: **227 MB** peak (model file 66 MB on disk)
- BGESmallENV15Q scratch daemon, model loaded, idle: **148 MB RSS**

BGESmallENV15Q = BAAI bge-small-en-v1.5, int8-quantized ONNX
(`Qdrant/bge-small-en-v1.5-onnx-Q`), 33M params, 384-dim. Retrieval quality is
below the base-size models; NeuroStrata's hybrid BM25 (Tantivy) search backstops
it, and the live store is tiny (1.7 MB, ~98 memories + code indexes).

## Staged state (done 2026-10-23)

- Model cache seeded (curl, system CA — fastembed's rustls client cannot
  download through the egress proxy): 
  `~/.cache/neuro/models/fastembed/models--Qdrant--bge-small-en-v1.5-onnx-Q/`
  at snapshot `aa8f8b060edb00e03bfdd08813a2949946c8ba55`, files at repo root
  (`model_optimized.onnx` 66,465,124 bytes, tokenizer.json, config.json
  `hidden_size: 384`, special_tokens_map.json, tokenizer_config.json,
  vocab.txt, ort_config.json).
- `~/.config/neurostrata/embedders.json`: BGESmallENV15Q appended as a third
  acceptable entry (384). **NomicEmbedTextV15 remains first = default.**
  Backup of the previous file: `embedders.json.bak-20261023`.
- Verified in the installed binary's strings: `BGESmallENV15Q` is a valid
  fastembed 7.0.1 enum variant pointing at the Qdrant repo above.
- End-to-end validation on an isolated scratch HOME (real store untouched):
  daemon booted healthy offline (`HF_HUB_OFFLINE=1`), clean shutdown,
  `add` returned a memory ID, `list` read it back, `doctor` reported the
  namespace healthy.

## Switch procedure (requires Pratik's explicit go)

1. **Back up** the live store: `neurostrata-mcp backup` plus confirm the
   off-machine backup copy is current.
2. **Export content** from the old store (content survives; vectors do not):
   `export-graph` + per-namespace `list` for `global`, `guard`, and any project
   namespaces. Decide what carries over — this is the natural point to settle
   the still-open keep-or-drop question on the 82 disputed `dap` tasks: a fresh
   store only re-adds what is explicitly carried.
3. **Stop the daemon** (`neurostrata-mcp shutdown`; confirm lock free).
4. **Move the old store aside, do not delete it** (deletion rule):
   rename `~/.config/NeuroStrata/data/db/` → `db-nomic768-2026-10-23/`.
   It stays as the rollback artifact until the new store has run clean for a
   week, then the deletion rule's confirm-delay-reconfirm flow applies.
5. **Select the new model** for the daemon start path:
   `NEUROSTRATA_MODEL=BGESmallENV15Q` in the daemon launch environment
   (watchdog + MCP stdio spawn paths in OPERATIONS.md), keeping the
   config-file default untouched for CLI parity, or reorder embedders.json —
   pick one mechanism and note it here when executed.
6. **Start the daemon** → it creates a fresh 384-dim store and loads the Q
   model from cache (offline; no download).
7. **Re-populate**: re-add carried memories (each re-embeds at 384d),
   re-seed the 3 guard rules, re-ingest code indexes for the active repos.
8. **Verify**: `status` healthy; `doctor` clean; fixed-query recall check —
   five known queries against the re-added memories must return the same top
   hits as a pre-switch baseline captured in step 2; daemon RSS sampled after
   1 h (expect ~150 MB class, not ~860 MB).

## Rollback

Stop daemon → move the 384-dim store aside → restore `db-nomic768-2026-10-23/`
as `db/` → remove `NEUROSTRATA_MODEL` (or restore embed order) → start daemon →
`status` healthy + spot search. Rollback is file moves only; the old store is
never modified by the new model (it is never opened with it).

## Notes

- On the installed 1.9.0 binary, protection against mixing vector spaces is
  the width check + this fresh-store discipline. PR #1
  (pratik-saptarshi/NeuroStrata) adds a persisted identity marker that refuses
  same-width identity changes too; once an installed binary carries it, this
  plan's step 4/5 ordering is additionally enforced by the daemon itself.
- Alternative considered: BGEBaseENV15Q (768d, ~110 MB) — same width, better
  retrieval, ~2× the Q-small footprint. It is a one-line config change if
  recall on the fixed-query check disappoints.
