# su-kb-pipeline

SU Knowledge Base Pipeline — Confluence ingest + RAG chat over the converted corpus. Phase 1.5 prototype for the SU Enterprise Data & AI team's KB-ingestion question.

## Read first (in this order)

1. [docs/STATUS.md](docs/STATUS.md) — current state, active decisions, recent pivots, open questions. **Read this before anything else when entering the project cold.**
2. [README.md](README.md) — architecture overview + setup commands
3. [docs/decisions/README.md](docs/decisions/README.md) — ADR index. Drill into specific ADRs (linked from STATUS.md) for decision rationale.
4. [HANDOFF.md](HANDOFF.md) — collaborator-facing onboarding (Shahaan, future interns). Different audience from STATUS.md.

## The four layers

| # | Layer | Lives in | Job |
|---|---|---|---|
| 1 | Ingest | [src/sukb/ingest/](src/sukb/ingest/) | Confluence → canonical markdown |
| 2 | Corpus | [output/](output/) | Raw mirror + curated wiki hubs + orientation files. **[output/CLAUDE.md](output/CLAUDE.md) has agent rules for the corpus content itself** (citation discipline, raw vs wiki) — different audience from this file. |
| 3 | Chat | [src/sukb/chat/](src/sukb/chat/) | RAG over the corpus with Claude Sonnet 4.6 + prompt caching |
| 4 | Web | [src/sukb/web/](src/sukb/web/) + [frontend/](frontend/) | FastAPI server + single-page Tailwind UI |

## Project tracking convention

Three artifacts under `docs/`, maintained via the `decision-log` skill:

- [docs/STATUS.md](docs/STATUS.md) — living one-page snapshot
- [docs/decisions/](docs/decisions/) — immutable ADRs in MADR format; pivots captured via `superseded by` chain
- [docs/log/](docs/log/) — append-only session entries (`YYYY-MM-DD.md`)

Skill commands: `/decision-log` (init/show), `/log` (today's session), `/decide <title>` (new ADR), `/supersede NNNN` (override an old ADR). The skill is installed at `~/.claude/skills/decision-log/` and works on any project.

## Conventions

- **Import package:** `sukb`. **Distribution name** (pip): `su-kb-pipeline`. Canonical setup is `pip install -e .` from the repo root; `tests/conftest.py` has a `sys.path` fallback so tests work without the editable install too.
- **Output filenames:** `<page-id> - <sanitized-title>.md`. Page ID is load-bearing — see [ADR-0001](docs/decisions/0001-page-id-prefixed-filenames.md).
- **Citations:** every claim in `output/wiki/` hubs must cite `[[<page-id>]]` inline. A claim without a source is a bug.
- **Test pages in the corpus:** path segments `(Test)` and `Summer Intern 2026` are excluded from the queryable corpus by default. They exist on disk but aren't content.

## Cost discipline

Two billing surfaces, two rules ([docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) §"Cost discipline rule"):

- **Claude Code subscription** (in-session work): file edits, planning, drafting markdown — no per-call cost.
- **`ANTHROPIC_API_KEY` in `.env`** (pay-per-token): use only for end-user simulation — `/api/query` chats, `scripts/run_eval.py`, `scripts/run_agentic_eval.py`. These are the production architecture under test.

Don't use the API for: drafting hubs, proposing candidates, writing analysis, refactoring scripts. That's in-session subscription work.

## Don't

- Don't commit secrets. `.env` is gitignored; `.env.example` is the template.
- Don't edit pages in `output/raw/`. It's the immutable Confluence mirror — fix at source and re-pull. Synthesis goes in `output/wiki/`.
- Don't auto-commit. The `decision-log` skill writes markdown only; staging and commits are the user's call.
- Don't merge in-flight ADR drafts as `accepted` without review. ADRs are immutable once accepted; mistakes get a `/supersede` chain, not an edit-in-place.
