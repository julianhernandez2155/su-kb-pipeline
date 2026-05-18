# Project Status — su-kb-pipeline

_Last updated: 2026-05-18_

## Current focus

Optimizing folder/file architecture so the corpus queries well under both ceiling-mode and agentic-MCP-mode retrieval. Shahaan is separately building the FastMCP server that will eventually wrap this corpus; the architectures need to converge.

## What's working

- **Ingest pipeline** — 29/32 ITSAI pages converted clean, 64 attachments verified on disk, re-runs are 1.5s no-ops via content-hash skip
- **Chat backend** (`/api/query`) + UI Query tab + session save/load
- **Test suite** — 110/110 green ([tests/](../tests/))
- **Baseline raw-only eval** — 14 ✅ / 1 ⚠️ / 0 ❌ on 15 representative queries ([docs/eval-baseline-2026-05-13.md](eval-baseline-2026-05-13.md))
- **2 reviewed wiki hubs** — `approved-ai-tools-for-university-data.md` and `claude-at-syracuse-product-surface-map.md`
- **4 orientation files** in `output/` — `CLAUDE.md`, `index.md`, space-level `index.md`, `wiki/index.md`
- **Package + repo published** — installable as `su-kb-pipeline` (import package `sukb`), private GitHub repo with Shahaan as collaborator

## What's next

1. **Step 6 — ceiling eval (raw+wiki mode)** — run `python scripts/run_eval.py --mode raw+wiki --server http://127.0.0.1:8765`. Cost ~$0.35. Diff against baseline. Especially watch q03 (the only ⚠️) and the two wiki-flagged queries (q04, q11).
2. **Step 7 — agentic tool-use simulator** — build `scripts/run_agentic_eval.py` (~150 lines) with four Anthropic tools (`read_index`, `list_hubs`, `search`, `read_page`). Run the 15 queries through agentic navigation. Capture full tool-call traces. This is the data Aaron needs to decide architecture.
3. **Step 8 — v1.5 writeup** — `docs/v1.5-results.md` with three-column comparison (baseline / ceiling / agentic) + trace analysis + production-architecture recommendation.

Full plan in [docs/next-phase-plan-v2.md](next-phase-plan-v2.md).

## Active decisions

- [ADR-0001](decisions/0001-page-id-prefixed-filenames.md) — Page-ID-prefixed filenames for collision/rename safety
- [ADR-0002](decisions/0002-fallback-first-adf-parsing.md) — Fallback-first ADF parsing (prefer storage-XML shape over JSON walker)
- [ADR-0004](decisions/0004-agentic-tool-surface-mcp-architecture.md) — Production MCP is an agentic tool-surface, not a RAG pipeline (supersedes ADR-0003)
- [ADR-0005](decisions/0005-src-layout-and-sukb-package-rename.md) — `src/` layout + `sukb` import package + `su-kb-pipeline` distribution name

## Recent pivots

- [ADR-0004](decisions/0004-agentic-tool-surface-mcp-architecture.md) supersedes [ADR-0003](decisions/0003-rag-pipeline-mcp-architecture.md) (2026-05-13) — production retrieval is agentic navigation over Resources+Tools, not FTS5+RAG behind MCP. Triggered by Codex review pass + the 14/15 raw-only baseline showing RAG isn't the bottleneck.

## Open questions

- Classifier budget — given 14/15 raw-only baseline, is the Haiku `audience`/`doc_type`/`tools`/`topics` classifier still worth $5/sweep, or do we defer indefinitely? Decide after Step 7.
- Production MCP audience — internal ITS/EDA only vs broader SU users; affects OAuth-flow urgency. Aaron 1:1.
- Sync infrastructure target — SU VM, Microsoft Fabric, Azure Function? Phase B assumed SU VM.
- Layered-index pattern confirmation — is the 4-orientation-file pattern (CLAUDE.md + global index + space index + wiki index) the standard for future spaces (ITHELP, Maxwell)?
