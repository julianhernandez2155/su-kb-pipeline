# Handoff — `su-kb-pipeline`

For Shahaan Khan, fellow intern on the SU EDA team. The repo is a snapshot of where my v1.5 prototype stands as of 2026-05-26. The internal docs (`docs/STATUS.md`, `docs/decisions/`, `docs/log/`) are my Claude-Code-session notes — they're the source of truth for "what's built, what's next, and why."

## Status at a glance

| Component | Status |
|---|---|
| v1 ingest pipeline (Confluence → markdown) | ✅ done; 29 public ITSAI pages converted clean (3 Summer Intern test pages classified `restricted_inherited` and excluded from the query path) |
| 4 orientation files (`output/CLAUDE.md`, `output/index.md`, space-level `index.md`, `output/wiki/index.md`) | ✅ done |
| Chat backend (`/api/query` + streaming) + UI Query tab + session save/load | ✅ done |
| 2 reviewed wiki hubs | ✅ `approved-ai-tools-for-university-data.md`, `claude-at-syracuse-product-surface-map.md` |
| **Phase 1.1: access classification (ADRs 0007–0010)** | ✅ done |
| Test suite | ✅ **257/257 green** |
| Baseline eval (raw-only, 15 queries, Claude Sonnet 4.6) | ✅ **14 ✅ / 1 ⚠️ / 0 ❌** — see [docs/eval-baseline-2026-05-13.md](docs/eval-baseline-2026-05-13.md) |
| Step 7b agentic eval (v3 prompt + read-path filter) | ✅ ran 2026-05-19; artifacts in `eval-runs/eval-agentic-v3-step7b-*.json`. Re-run after Step 3 ship is optional. |
| Step 8 retrieval metrics | ✅ shipped — `scripts/compute_retrieval_metrics.py` + 341-line test |
| Step 6: ceiling eval (raw+wiki, 15 queries) | 🟡 **ready to run** — `python scripts/run_eval.py --mode raw+wiki` |
| Step 8 writeup (`docs/v1.5-results.md`) | 🔵 next — three-column comparison + architecture recommendation |
| PR #1 | 🟡 open — covers Phase 1 + Phase 1.1 + v1.5 eval push. https://github.com/julianhernandez2155/su-kb-pipeline/pull/1 |

## The architectural pivot (read this first)

The original v1 plan modeled production retrieval as FTS5 + RAG behind an MCP server. After Steps 1–5 and a Codex review pass, the architecture pivoted to **agentic tool-surface MCP** ([ADR-0004](docs/decisions/0004-agentic-tool-surface-mcp-architecture.md)):

> *MCP exposes Resources (the file tree + indexes) and Tools (`search`, `read_page`). The production Claude model navigates the corpus the same way Claude Code navigates a workspace — reads orientation files first, follows wikilinks, calls search when needed. FTS5 isn't dead, but it's **one tool** the agentic model calls, not the whole retrieval surface.*

Full reasoning + verification against the MCP spec + Anthropic tool-use docs is in [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) §"The architectural pivot, explained".

Consequence for your Phase B FastMCP + FTS5 plan: the orientation files (`output/CLAUDE.md`, `output/index.md`, `output/wiki/index.md`, space indexes) are now load-bearing. If we converge on the production shape, the build is mostly wrapping four functions (`read_index`, `list_hubs`, `search`, `read_page`) in Streamable HTTP + auth — 80% of the architecture is already prototyped here.

## Phase 1.1: access classification (the big update since 2026-05-14)

A two-day sprint (2026-05-19 → 2026-05-20) shipped end-to-end access classification on top of the v1 pipeline. Four ADRs ([0007](docs/decisions/0007-access-classification-v1.md), [0008](docs/decisions/0008-space-classifier-tightening.md), [0009](docs/decisions/0009-mcp-read-path-filter.md), [0010](docs/decisions/0010-trust-zones-admin-vs-mcp.md)) document the decisions. Headline shape:

**Five `visibility_signal` values** (frontmatter schema v3):

| Value | Meaning |
|---|---|
| `no_read_restrictions_seen` | Direct + ancestor walk clean. **Only this value is queryable by the user-facing MCP/chat surface.** |
| `restricted_direct` | Page has a non-empty `read` restriction directly. |
| `restricted_inherited` | Ancestor page or folder has a `read` restriction. (Summer Intern test pages classify here via folder `1069121551`.) |
| `space_restricted` | Space-level audience not positively identified as broadly accessible. |
| `unknown` | Direct or ancestor check failed; conservative — treated as restricted. |

**Two trust zones** ([ADR-0010](docs/decisions/0010-trust-zones-admin-vs-mcp.md)):

- **User-facing MCP/chat** (`AgenticTools`, `_run_chat_stream`, `_run_agentic_stream`, `answer_query`) — MUST go through `load_raw_corpus` / `load_wiki_corpus` with the public filter. Restricted IDs are externally indistinguishable from nonexistent IDs (no enumeration oracle).
- **Admin/dev UI** (`/api/pages`, `/api/sync/*`, `/api/query/status`, corpus browser) — intentionally bypasses the filter to support ingest-health inspection. Trust assumption is the operator's Confluence account.

**Load-time chokepoint pattern** ([ADR-0009](docs/decisions/0009-mcp-read-path-filter.md)) — filter at `load_raw_corpus` / `load_wiki_corpus`, not at each retrieval surface. New surfaces inherit the filter automatically. The corpus has been verified end-to-end: the 3 Summer Intern pages cannot appear via `search`, `read_page`, `list_index`, `list_hubs`, or hub `source_pages`.

**RBAC-ready metadata, not RBAC-implemented.** The manifest at `output/_access/access-manifest.jsonl` carries normalized `read.user_ids` + `read.group_ids` per page/ancestor/space, so a future per-user evaluator can be added without re-ingesting. Three real prerequisites still gate per-user enforcement (identity bridge, effective-access evaluator, pagination audit) — captured in [ADR-0010 §Future-readiness notes](docs/decisions/0010-trust-zones-admin-vs-mcp.md).

**Code lives at:**

- `src/sukb/ingest/access.py` — `PageClassification`, `classify_visibility`, manifest serializers
- `src/sukb/ingest/restrictions.py` — `/restriction/byOperation` parser + ancestor cache
- `src/sukb/ingest/spaces.py` — space-permissions classifier (positive-ID via `role:ANONYMOUS read/space` marker)
- `src/sukb/ingest/frontmatter.py` — schema v3, `ACCESS_OWNED_FIELDS` constant
- `src/sukb/ingest/puller.py` — canonical writer of access-owned fields
- `src/sukb/chat/query.py`, `agentic_tools.py`, `web/server.py` — the public-filter chokepoint
- `scripts/access_metadata_probe.py` — one-off audit tool

## What to read, in order

1. [README.md](README.md) — four-layer architecture, setup, project structure
2. **[docs/STATUS.md](docs/STATUS.md)** — current state, active decisions, recent pivots, open questions. Read this when entering the project cold.
3. [docs/decisions/README.md](docs/decisions/README.md) — ADR index. Drill into specific ADRs for decision rationale.
4. [output/CLAUDE.md](output/CLAUDE.md) — agent rules for working with the corpus (raw vs wiki vs `_access/`, citation discipline)
5. [docs/wiki-operating-model.md](docs/wiki-operating-model.md) — rules for the wiki layer
6. [docs/eval-baseline-2026-05-13.md](docs/eval-baseline-2026-05-13.md) — current eval score, per-query notes
7. [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) — Steps 6/7/8 with the architectural pivot
8. [docs/v1-tool-brief.md](docs/v1-tool-brief.md) — Aaron-facing brief on what v1 ships and why
9. [output/raw/knowledge-bases/Artificial%20Intelligence%20%28AI%29/](output/raw/knowledge-bases/Artificial%20Intelligence%20%28AI%29/) — browse the 29 converted pages
10. [output/wiki/](output/wiki/) — read both reviewed synthesis hubs

For historical context (planning docs that preceded the ADRs), see [docs/archive/](docs/archive/).

## Phase versioning (the confusing part)

- **v1.5 / Phase 1.5** = the prototype milestone covering Steps 1–8 (ingest, chat, baseline eval, wiki hubs, orientation files, ceiling eval, agentic eval, writeup).
- **Phase 1** = the metadata-schema hardening sprint inside Phase 1.5 — observed-fact frontmatter v2 (word_count, attachment_count, visibility_signal, etc.), classifier preservation, schema-version backfill gate. Shipped 2026-05-14 → 2026-05-19. ADRs 0001, 0002, 0004, 0005, 0006.
- **Phase 1.1** = the access-classification sprint after Phase 1 — schema v3 (drops `restricted_to`, adds `restriction_source_ids`, list-shape `restriction_check`), classifier + MCP read-path filter + trust zones. Shipped 2026-05-19 → 2026-05-21. ADRs 0007, 0008, 0009, 0010.
- **Phase 1.2** = deferred lifecycle metadata (`author_id`, `created_at`, version-detail, tighter attachment metadata). Not started.

Yes, "Phase 1.1 ships after Phase 1 inside Phase 1.5" reads weird. It's chronological: Phase 1 was the natural first sub-sprint; Phase 1.1 was the next; if there's a 1.2 it comes after that. Phase 1.5 is the milestone name that predates them all.

## Cost discipline (important if you run anything)

Two billing surfaces, two rules. From [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md):

- **Claude Code subscription** (when working in a Claude Code session with this repo open): covers in-session work — file edits, planning, drafting markdown. No per-call cost.
- **`ANTHROPIC_API_KEY` in `.env`**: pay-per-token. Use only for **end-user simulation** — `/api/query` chats, `scripts/run_eval.py`, `scripts/run_agentic_eval.py`. These are the production architecture under test.

Don't use the API for: drafting hubs, proposing candidates, writing analysis, refactoring scripts. That's in-session Claude Code work — covered by the subscription.

Baseline cost data: 15 queries cost $0.39 total (prime $0.15 + 14 × $0.014 cached). At ~$0.017/query in cached mode, a 100-query eval would cost ~$1.85. Aaron's pre-approval ceiling was ~$5.

## How this connects to your Phase B work

Your FastMCP + SQLite FTS5 + Confluence design is one architectural answer to the project's "where do these articles live + how do agents query them" question. This prototype produces the artifact your service would index. The hand-off surface between the two:

- **Format:** frontmatter v3 + body markdown, content-hashed, page-ID-prefixed filenames, `[[page-id]]` wikilinks. Stable, re-indexable, deterministic.
- **Access:** `visibility_signal` is the public filter; if your service indexes raw, the same field is the gate. If/when per-user enforcement lands, the manifest at `output/_access/access-manifest.jsonl` carries the normalized ACL data.
- **Delta detection:** `.sync-state.json` per space gives "what changed since last pull" cheaply — useful for incremental FTS5 updates.
- **Structural invariants:** the strictness boundary (tolerate unknowns, hard-fail unparseable) means downstream code can trust the markdown shape.
- **`src/sukb/ingest/`** can be imported as-is into a service runtime if we go that direction. The shared classifier (`access.py`, `restrictions.py`, `spaces.py`) is reusable.

The open question the v1.5 writeup (Step 8) is meant to answer: **is the agentic tool-surface architecture good enough to justify the VM/MCP investment over the FTS5+RAG architecture?** If yes, your Phase B FastMCP layer wraps `read_index` / `list_hubs` / `search` / `read_page` in Streamable HTTP + auth, and FTS5 is one tool inside that surface — not the whole retrieval pipeline. If no, the writeup surfaces specific failure modes Aaron's team can either fix in Confluence or close with targeted wiki hubs.

## Open questions for the next Aaron 1:1

From [docs/STATUS.md §"Open questions"](docs/STATUS.md) — the genuinely open items, not the now-shipped ones:

1. **Classifier budget** — given 14/15 raw-only baseline, is the Haiku `audience`/`doc_type`/`tools`/`topics` classifier still worth $5/sweep, or do we defer indefinitely? Decide after Step 8 writeup.
2. **Hub coverage gaps** — only 2 reviewed wiki hubs today. Which cross-cutting questions does the agentic eval miss because no hub exists?
3. **Layered-index pattern confirmation** — is the 4-orientation-file pattern (`CLAUDE.md` + global index + space index + wiki index) the standard for future spaces (ITHELP, Maxwell)?
4. **Metadata fields for queryability** — Phase 1.2 deferred items (`author_id`, `created_at`, version metadata) are unblocked; which actually move retrieval quality vs adding noise?

Stakeholder-owned items deferred from Julian's scope (not optimization decisions — see [docs/STATUS.md §"Out of scope"](docs/STATUS.md)):

- Production MCP audience (internal ITS only vs broader SU) → OAuth urgency
- Sync infrastructure target (SU VM, Microsoft Fabric, Azure Function)
- Per-user RBAC implementation timeline
- Convergence with Phase B FastMCP server

## Running it yourself

You have Confluence Collaborators + JSM Agent License access (Aaron approved 2026-05-12 per the onboarding doc). Setup is in [README.md](README.md) — full PowerShell + bash blocks there.

Quick version:

```powershell
git clone https://github.com/julianhernandez2155/su-kb-pipeline.git
cd su-kb-pipeline
git checkout phase-1-metadata-schema   # current working branch; PR #1 → main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# Edit .env -- ATLASSIAN_EMAIL, ATLASSIAN_TOKEN, ANTHROPIC_API_KEY
python -m pytest tests/ -q   # should be 257 green
python -m uvicorn sukb.web.server:app --port 8000 --reload
```

For chat / eval you also need `ANTHROPIC_API_KEY`. If you don't have one yet, the chat tab gracefully degrades — you can still pull and browse the corpus, just can't query. I can lend you mine for testing or you can request one through Aaron.

— Julian (last updated 2026-05-26)
