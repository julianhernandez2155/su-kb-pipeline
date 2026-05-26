# su-kb-pipeline

SU Knowledge Base Pipeline — Confluence ingest + RAG chat over the converted corpus.

Phase 1.5 prototype for the SU Enterprise Data & AI team's KB-ingestion question: *"How should knowledge-base articles be formatted, stored, accessed, and updated so an AI can answer questions from them?"* Current status: ingest pipeline + chat backend + UI all working end-to-end against the SU `ITSAI` Confluence space (29 pages); baseline raw-only eval is **14 ✅ / 1 ⚠️ / 0 ❌** on 15 representative queries. See [HANDOFF.md](HANDOFF.md) for what's built and what's next.

## The four layers

| # | Layer | Lives in | What it does |
|---|---|---|---|
| 1 | **Ingest** | [src/sukb/ingest/](src/sukb/ingest/) | Pull Confluence pages, walk storage XML + ADF, run macro handlers, resolve `[[page-id]]` wikilinks, download attachments, write to `output/raw/` |
| 2 | **Corpus** | [output/](output/) | On-disk artifact: immutable `raw/` mirror + LLM-drafted `wiki/` synthesis hubs + `attachments/` + dead-letter `conversion-failures/` + orientation files (`CLAUDE.md`, `index.md`) |
| 3 | **Chat** | [src/sukb/chat/](src/sukb/chat/) | RAG over the corpus with Claude Sonnet 4.6 + prompt caching; session persistence (`output/query-sessions/`) |
| 4 | **Web** | [src/sukb/web/](src/sukb/web/) + [frontend/](frontend/) | FastAPI server exposing ingest jobs (SSE-streamed) and chat queries; single-page Tailwind UI |

Shared utilities: [src/sukb/config.py](src/sukb/config.py) (SyncConfig — used by all three Python layers).

## Setup

### Windows / PowerShell (primary)

```powershell
git clone https://github.com/julianhernandez2155/su-kb-pipeline.git
cd su-kb-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# Edit .env -- fill in ATLASSIAN_EMAIL, ATLASSIAN_TOKEN, ANTHROPIC_API_KEY
python -m pytest tests/ -v
python -m uvicorn sukb.web.server:app --port 8000 --reload
```

Then open <http://127.0.0.1:8000/>. The header should show your `@syr.edu` email + green dot. Click **Pull** on the ITSAI row to ingest; switch to **Query** to chat with the corpus.

### macOS / Linux

```bash
git clone https://github.com/julianhernandez2155/su-kb-pipeline.git
cd su-kb-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env
python -m pytest tests/ -v
python -m uvicorn sukb.web.server:app --port 8000 --reload
```

## Required credentials

- **`ATLASSIAN_EMAIL`** — your `@syr.edu` email. Required by [src/sukb/ingest/puller.py](src/sukb/ingest/puller.py) for Confluence Cloud auth.
- **`ATLASSIAN_TOKEN`** — Atlassian Cloud API token, format `ATATT*`. Get one at <https://id.atlassian.com/manage-profile/security/api-tokens>. You need *Confluence Collaborators* + *JSM Agent License* access at SYR.
- **`ANTHROPIC_API_KEY`** — Anthropic API key, format `sk-ant-api03-*`. Optional: the UI degrades gracefully without it (Query tab disabled), but `scripts/run_eval.py` and `scripts/run_proposals.py` require it.

## What this prototype demonstrates

- **End-to-end pull → convert → write** for a real SU space. Macro registry handles 15+ Confluence macros; ADF fallback-first detection catches mixed storage formats; attachment verifier rejects emitted refs that don't exist on disk; dead-letter routing means failures never silently corrupt the corpus.
- **Re-runnable**. Per-page content hash + version → skip on rerun. A second pull of the same space is a 1.5-second no-op when nothing changed.
- **Spec-compliant frontmatter** (page_id, source_url, ancestor_path, content_hash, last_modified, version, contributors, days_since_modified, maintenance_signal). Classifier fields (`audience`, `doc_type`, `tools`, `topics`) emit null/empty in v1 — wired for Haiku 4.5 in v1.1.
- **Layered orientation files** in `output/`: `CLAUDE.md` (agent rules), `index.md` (global map), space-level `index.md`, `wiki/index.md`. Designed to be load-bearing for an agentic MCP client — see [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) for the architectural pivot.
- **RAG chat with prompt caching**. The corpus is cached as a system prompt (Sonnet 4.6); subsequent queries pay ~10% of input tokens. Every claim cites at least one `[[page-id]]` inline.

## Architecture notes

- **Recursive walker + flat handler dict** — adding a new macro is one entry in `MACRO_HANDLERS` (in [src/sukb/ingest/macros.py](src/sukb/ingest/macros.py)). Not a full visitor pattern.
- **Fallback-first ADF**: detect `ac:adf-*` → prefer `<ac:adf-fallback>` (storage-XML shaped; reuses the macro registry) → fall back to JSON walker → hard-fail to dead-letter on bad JSON.
- **Shared emitters**: `render_callout` and `render_collapsible` are imported by both the macro registry and the ADF walker, so `panel` / `expand` output looks the same regardless of source format.
- **Strictness boundary** — tolerated: unknown macros, deprecated params, legacy variants, complex tables. Hard-fail: unparseable XML, missing required identity fields, unresolvable attachments, bad ADF JSON.
- **Content hash is computed over the converted Markdown body** (not frontmatter, not storage XML) so whitespace-only Confluence edits don't trigger re-classification later.
- **Job queue is in-memory + single-process**. Fine for the 32-page v1 corpus. Redis/RQ if multi-tenant runtime appears.

## Cost discipline

Two billing surfaces, two rules ([docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) has the long version):

- **Claude Code subscription** (working in a Claude Code session): covers planning, file edits, markdown drafting. No per-call cost.
- **`ANTHROPIC_API_KEY`** (this `.env`): pay-per-token. Use only for end-user simulation — `/api/query` chats, `scripts/run_eval.py`, the planned Step-7 agentic simulator. These are the production architecture under test.

## Project structure

```
su-kb-pipeline/
├── README.md, HANDOFF.md
├── pyproject.toml             # installable package metadata
├── requirements.txt
├── pytest.ini
├── sync_config.yaml           # three-knob inclusion config (§4.1)
├── .env.example
├── src/sukb/
│   ├── config.py              # SyncConfig loader
│   ├── ingest/                # LAYER 1
│   │   ├── puller.py          # v2 API client + pull-space orchestrator
│   │   ├── converter.py       # storage XML walker
│   │   ├── macros.py          # MACRO_HANDLERS registry
│   │   ├── adf.py             # ADF fallback-first pipeline
│   │   ├── frontmatter.py     # spec §4.4 schema
│   │   ├── attachments.py     # download + on-disk verify
│   │   ├── wikilinks.py       # [[<page-id> - <title>]] resolution
│   │   ├── state.py           # .sync-state.json skip-on-rerun
│   │   └── dead_letter.py     # conversion-failures/ routing
│   ├── chat/                  # LAYER 3
│   │   ├── query.py           # RAG + Claude Sonnet 4.6 + prompt caching
│   │   └── sessions.py        # chat persistence
│   └── web/                   # LAYER 4 (backend half)
│       └── server.py          # FastAPI + SSE
├── frontend/                  # LAYER 4 (UI half)
│   └── index.html             # single-file Tailwind UI
├── scripts/                   # operational entry points
│   ├── run_eval.py            # eval set runner (reads docs/eval-queries.yaml)
│   ├── run_proposals.py       # Karpathy-style hub proposal pass
│   └── draft_hubs.py          # LLM-drafted hub generator
├── tests/                     # 257 tests; mirrors src/sukb structure
│   ├── ingest/, chat/, web/, fixtures/
│   └── conftest.py
├── docs/                      # decision log + active planning
│   ├── STATUS.md              # living one-page snapshot (read first)
│   ├── decisions/             # ADRs (0001–0010, MADR format)
│   ├── log/                   # append-only session entries (YYYY-MM-DD.md)
│   ├── archive/               # historical planning docs (superseded by ADRs)
│   ├── next-phase-plan-v2.md  # active Step 6/7/8 plan
│   ├── v1-tool-brief.md       # Aaron-facing v1 design brief
│   ├── wiki-operating-model.md
│   ├── eval-baseline-2026-05-13.md
│   └── eval-queries.yaml
└── output/                    # LAYER 2 (the corpus)
    ├── CLAUDE.md              # agent rules for working with output/
    ├── index.md               # global corpus map
    ├── raw/                   # immutable Confluence mirror
    ├── wiki/                  # 2 reviewed synthesis hubs + index
    ├── _access/               # access-classification artifacts (Phase 1.1)
    ├── attachments/           # referenced binaries
    ├── conversion-failures/   # dead-letter pages (empty in clean state)
    └── query-sessions/        # eval-run transcripts (gitignored)
```
