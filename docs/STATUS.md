# Project Status — su-kb-pipeline

_Last updated: 2026-05-20_

## Current focus

Phase 1.1 Steps 1–3 complete: corpus is now public-query safe. The chat / agentic surfaces (`search`, `read_page`, `list_index`, `list_hubs`, hub `source_pages`) only ever see `visibility_signal: no_read_restrictions_seen` pages. Restricted IDs are indistinguishable from nonexistent IDs to the model; the eval trace summary records the distinction for observability. Real-corpus verification: the 3 Summer Intern pages (`1068171339`, `1069318154`, `1069350926`) do not appear via any surface.

Next: v1.5 eval push (Steps 6–8) now unblocked — agentic eval can run without leaking restricted content.

## What's working

- **Ingest pipeline** — 29/32 ITSAI pages converted clean, 64 attachments verified on disk, re-runs are 1.5s no-ops via content-hash skip
- **Chat backend** (`/api/query`) + UI Query tab + session save/load
- **Test suite** — 253/253 green ([tests/](../tests/))
- **Baseline raw-only eval** — 14 ✅ / 1 ⚠️ / 0 ❌ on 15 representative queries ([docs/eval-baseline-2026-05-13.md](eval-baseline-2026-05-13.md))
- **2 reviewed wiki hubs** — `approved-ai-tools-for-university-data.md` and `claude-at-syracuse-product-surface-map.md`
- **4 orientation files** in `output/` — `CLAUDE.md`, `index.md`, space-level `index.md`, `wiki/index.md`
- **Package + repo published** — installable as `su-kb-pipeline` (import package `sukb`), private GitHub repo with Shahaan as collaborator
- **Phase 1.1 access classification — Steps 1 + 2 + 3 complete** (2026-05-19 → 2026-05-20): 34/34 ITSAI pages classified (31 clean, 3 restricted-inherited via folder 1069121551). MCP read-path filter at corpus-loader chokepoint per ADR-0009. Probe at [scripts/access_metadata_probe.py](../scripts/access_metadata_probe.py); puller integration in [src/sukb/ingest/puller.py](../src/sukb/ingest/puller.py); shared classifier helpers in [access.py](../src/sukb/ingest/access.py) / [restrictions.py](../src/sukb/ingest/restrictions.py) / [spaces.py](../src/sukb/ingest/spaces.py); read-path filter in [src/sukb/chat/query.py](../src/sukb/chat/query.py) + [agentic_tools.py](../src/sukb/chat/agentic_tools.py). ADRs: [0007](decisions/0007-access-classification-v1.md), [0008](decisions/0008-space-classifier-tightening.md), [0009](decisions/0009-mcp-read-path-filter.md). Frontmatter schema v3 (`restricted_to` dropped). Test count: 253 (56 new tests: 29 classifier + 27 read-path filter).

## What's next

**v1.5 eval push** — Phase 1.1 is done; eval work resumes:

1. **Step 6 — ceiling eval (raw+wiki mode)** — `python scripts/run_eval.py --mode raw+wiki --server http://127.0.0.1:8765`. Cost ~$0.35. Diff against baseline. Especially watch q03 (the only ⚠️) and the two wiki-flagged queries (q04, q11).
2. **Step 7 — agentic tool-use simulator** — `scripts/run_agentic_eval.py` (~150 lines) with four Anthropic tools (`read_index`, `list_hubs`, `search`, `read_page`). Run the 15 queries through agentic navigation. Capture full tool-call traces.
3. **Step 8 — v1.5 writeup** — `docs/v1.5-results.md` with three-column comparison (baseline / ceiling / agentic) + trace analysis + production-architecture recommendation.

Full eval plan in [docs/next-phase-plan-v2.md](next-phase-plan-v2.md).

**Follow-up ADR (deferred):** remove `Summer Intern 2026` from `_TEST_PATH_SEGMENTS` after two clean weeks under the classifier-only path; keep `(Test)` (content-quality exclusion, not access). Per Phase 1.1 plan §"Belt-and-braces."

## Active decisions

- [ADR-0001](decisions/0001-page-id-prefixed-filenames.md) — Page-ID-prefixed filenames for collision/rename safety
- [ADR-0002](decisions/0002-fallback-first-adf-parsing.md) — Fallback-first ADF parsing (prefer storage-XML shape over JSON walker)
- [ADR-0004](decisions/0004-agentic-tool-surface-mcp-architecture.md) — Production MCP is an agentic tool-surface, not a RAG pipeline (supersedes ADR-0003)
- [ADR-0005](decisions/0005-src-layout-and-sukb-package-rename.md) — `src/` layout + `sukb` import package + `su-kb-pipeline` distribution name
- [ADR-0007](decisions/0007-access-classification-v1.md) — Access classification v1: direct + ancestor + space layers; descriptive metadata feeds MCP read-path filter (supersedes ADR-0006)
- [ADR-0008](decisions/0008-space-classifier-tightening.md) — Space classifier positive-ID via `role:ANONYMOUS read/space` marker + operator allowlist fallback; `unknown` space audience → page classified `space_restricted`
- [ADR-0009](decisions/0009-mcp-read-path-filter.md) — MCP read-path filter at the corpus-loader chokepoint; restricted IDs externally indistinguishable from nonexistent IDs across all retrieval surfaces

## Recent pivots

- [ADR-0009](decisions/0009-mcp-read-path-filter.md) (2026-05-20) — Phase 1.1 Step 3 ships. Read-path enforcement closes the loop ADRs 0007 + 0008 opened; the corpus is now end-to-end public-query safe.
- [ADR-0008](decisions/0008-space-classifier-tightening.md) (2026-05-20) — Triggered by Step 2 review pass that flagged the original "non-empty results → su_community" heuristic as too permissive for multi-space production. ITSAI continues to classify correctly via the new positive-ID signal; new spaces must either have the marker or be explicitly allowlisted.
- [ADR-0007](decisions/0007-access-classification-v1.md) supersedes [ADR-0006](decisions/0006-visibility-metadata-is-descriptive.md) (2026-05-19) — visibility metadata IS computed now (not stubbed), via direct + ancestor + space checks. Triggered by the same-day API-shape probe that showed Summer Intern child pages would silently classify as `accessible_to_sync_user` under ADR-0006 despite their parent folder having direct read restrictions.
- [ADR-0004](decisions/0004-agentic-tool-surface-mcp-architecture.md) supersedes [ADR-0003](decisions/0003-rag-pipeline-mcp-architecture.md) (2026-05-13) — production retrieval is agentic navigation over Resources+Tools, not FTS5+RAG behind MCP. Triggered by Codex review pass + the 14/15 raw-only baseline showing RAG isn't the bottleneck.

## Open questions

- Classifier budget — given 14/15 raw-only baseline, is the Haiku `audience`/`doc_type`/`tools`/`topics` classifier still worth $5/sweep, or do we defer indefinitely? Decide after Step 7.
- Production MCP audience — internal ITS/EDA only vs broader SU users; affects OAuth-flow urgency. Aaron 1:1.
- Sync infrastructure target — SU VM, Microsoft Fabric, Azure Function? Phase B assumed SU VM.
- Layered-index pattern confirmation — is the 4-orientation-file pattern (CLAUDE.md + global index + space index + wiki index) the standard for future spaces (ITHELP, Maxwell)?

## Known future improvements (conditional, gated on evidence)

- **Procedural-prerequisite detection in SYSTEM_PROMPT.** q06 (Claude Code Install on Windows) in the v3 smoke (2026-05-18) demonstrated that under the v3 citation rule the model chooses the OMIT path for a prerequisite page rather than reading it — leaving the user without a concrete "how to obtain Claude Code" pointer. The right read-then-cite branch would have been ideal. *Trigger to add a prompt nudge:* Step 7b shows ≥2 queries where the model omits a procedural-prerequisite page that it knows about (named in search results / index but not read). If Step 7b doesn't reproduce the pattern, leave the prompt alone.
