# Handoff — `su-kb-pipeline`

For Shahaan Khan, fellow intern on the SU EDA team. The repo is a snapshot of where my Phase 1.5 work stands as of 2026-05-14. The internal docs (`docs/*.md`) are my Claude-Code-session notes — they're the source of truth for "what's built, what's next, and why."

## Status at a glance

| Component | Status |
|---|---|
| v1 ingest pipeline (Confluence → markdown) | ✅ done; 29 ITSAI pages converted clean |
| 4 orientation files (`output/CLAUDE.md`, `output/index.md`, space-level `index.md`, `output/wiki/index.md`) | ✅ done |
| Chat backend (`/api/query`) + UI Query tab + session save/load | ✅ done |
| 2 reviewed wiki hubs | ✅ `approved-ai-tools-for-university-data.md`, `claude-at-syracuse-product-surface-map.md` |
| Test suite | ✅ **110/110 green** |
| Baseline eval (raw-only, 15 queries, Claude Sonnet 4.6) | ✅ **14 ✅ / 1 ⚠️ / 0 ❌** — see [docs/eval-baseline-2026-05-13.md](docs/eval-baseline-2026-05-13.md) |
| Step 6: ceiling eval (raw+wiki, 15 queries) | 🟡 **ready to run** — `python scripts/run_eval.py --mode raw+wiki` |
| Step 7: agentic tool-use simulator (the production-shape test) | 🔵 **next build** — ~150 lines, four tools; see [docs/next-phase-plan-v2.md §Step 7](docs/next-phase-plan-v2.md) |
| Step 8: v1.5 writeup for Aaron (3-column comparison) | 🔵 after Step 7 |

## The architectural pivot (read this first)

The original v1 plan modeled production retrieval as FTS5 + RAG behind an MCP server. After Steps 1–5 and a Codex review pass, the architecture pivoted to **agentic tool-surface MCP**:

> *MCP exposes Resources (the file tree + indexes) and Tools (`search`, `read_page`). The production Claude model navigates the corpus the same way Claude Code navigates a workspace — reads orientation files first, follows wikilinks, calls search when needed. FTS5 isn't dead, but it's **one tool** the agentic model calls, not the whole retrieval surface.*

Full reasoning + verification against the MCP spec + Anthropic tool-use docs is in [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) §"The architectural pivot, explained".

Consequence for your Phase B FastMCP + FTS5 plan: the orientation files (`output/CLAUDE.md`, `output/index.md`, `output/wiki/index.md`, space indexes) are now load-bearing. If we converge on the production shape, the build is mostly wrapping four functions (`read_index`, `list_hubs`, `search`, `read_page`) in Streamable HTTP + auth — 80% of the architecture is already prototyped here.

## What to read, in order

1. [README.md](README.md) — four-layer architecture, setup, project structure
2. [docs/v1-tool-brief.md](docs/v1-tool-brief.md) — Aaron-facing brief on what v1 ships and why each design choice was made
3. [output/CLAUDE.md](output/CLAUDE.md) — agent rules for working with the corpus (raw vs wiki, citation discipline, status field convention)
4. [docs/wiki-operating-model.md](docs/wiki-operating-model.md) — rules for the wiki layer (citation discipline, hub litmus test, status lifecycle)
5. [docs/eval-baseline-2026-05-13.md](docs/eval-baseline-2026-05-13.md) — current eval score, per-query notes, observations
6. [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) — Steps 6/7/8 with the architectural pivot (this is the source-of-truth plan)
7. [output/raw/knowledge-bases/Artificial%20Intelligence%20%28AI%29/](output/raw/knowledge-bases/Artificial%20Intelligence%20%28AI%29/) — browse the 29 converted pages
8. [output/wiki/](output/wiki/) — read both reviewed synthesis hubs

## Cost discipline (important if you run anything)

Two billing surfaces, two rules. From [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md):

- **Claude Code subscription** (when working in a Claude Code session with this repo open): covers in-session work — file edits, planning, drafting markdown. No per-call cost.
- **`ANTHROPIC_API_KEY` in `.env`**: pay-per-token. Use only for **end-user simulation** — `/api/query` chats, `scripts/run_eval.py`, the planned Step 7 agentic simulator. These are the production architecture under test.

Don't use the API for: drafting hubs, proposing candidates, writing analysis, refactoring scripts. That's in-session Claude Code work — covered by the subscription.

Baseline cost data: 15 queries cost $0.39 total (prime $0.15 + 14 × $0.014 cached). At ~$0.017/query in cached mode, a 100-query eval would cost ~$1.85. Aaron's pre-approval ceiling was ~$5.

## How this connects to your Phase B work

Your FastMCP + SQLite FTS5 + Confluence design is one architectural answer to the project's "where do these articles live + how do agents query them" question. This prototype produces the artifact your service would index. The hand-off surface between the two:

- **Format:** frontmatter + body markdown, content-hashed, page-ID-prefixed filenames, `[[page-id]]` wikilinks. Stable, re-indexable, deterministic.
- **Delta detection:** `.sync-state.json` per space gives "what changed since last pull" cheaply — useful for incremental FTS5 updates.
- **Structural invariants:** the strictness boundary (tolerate unknowns, hard-fail unparseable) means downstream code can trust the markdown shape.
- **`src/sukb/ingest/`** can be imported as-is into a service runtime if we go that direction.

The open question Step 7 is meant to answer: **is the agentic tool-surface architecture good enough to justify the VM/MCP investment over the FTS5+RAG architecture?** If yes, your Phase B FastMCP layer wraps `read_index` / `list_hubs` / `search` / `read_page` in Streamable HTTP + auth, and FTS5 is one tool inside that surface — not the whole retrieval pipeline. If no, Step 7 surfaces specific failure modes Aaron's team can either fix in Confluence or close with targeted wiki hubs.

## Open questions for the next Aaron 1:1

From [docs/next-phase-plan-v2.md](docs/next-phase-plan-v2.md) §"Open questions":

1. The "Answers" Confluence space (Data Center site, no category) — prior art or defunct?
2. MCP rollout audience — internal ITS/EDA only, or broader SU users? Defines OAuth-flow urgency.
3. Attachment policy — v1's "preserve as raw refs" still fine? PDF/DOCX extraction is post-v1.5.
4. Sync infrastructure — SU VM, Microsoft Fabric, Azure Function? Phase B assumed SU VM.
5. Filename scheme confirmation — page-ID prefix stays?
6. Eval set authorship — seed future evals from real Confluence search logs if available?
7. Classifier budget — given raw-only's 14/15 baseline, is the Haiku `audience`/`doc_type`/`tools`/`topics` classifier still worth $5/sweep, or do we defer indefinitely?
8. **(New)** Architecture: agentic tool-surface vs RAG-pipeline MCP. Step 7 results inform this.
9. **(New)** Layered-index pattern confirmation — standard for future spaces (ITHELP, Maxwell)?

## Files not shipped here

A few docs in `docs/*.md` link to research files that live in my internship workspace and didn't get copied (would have pulled in spec drafts and prior-art writeups). Some markdown links may dangle. If you want any of these, ping me on Teams:

- `pipeline-spec.md` (v0.4 — the implementation spec)
- `v1-prototype-plan.md` (the original v1 plan, superseded)
- `pipeline-spec-proposals.md` (pending spec amendments)
- `next-phase-plan.md` (v1 of the next-phase plan; superseded by `docs/next-phase-plan-v2.md`)

## Running it yourself

You have Confluence Collaborators + JSM Agent License access (Aaron approved 2026-05-12 per the onboarding doc). Setup is in [README.md](README.md) — full PowerShell + bash blocks there.

Quick version:

```powershell
git clone https://github.com/julianhernandez2155/su-kb-pipeline.git
cd su-kb-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# Edit .env -- ATLASSIAN_EMAIL, ATLASSIAN_TOKEN, ANTHROPIC_API_KEY
python -m pytest tests/ -v   # should be 110 green
python -m uvicorn sukb.web.server:app --port 8000 --reload
```

For chat / eval you also need `ANTHROPIC_API_KEY`. If you don't have one yet, the chat tab gracefully degrades — you can still pull and browse the corpus, just can't query. I can lend you mine for testing or you can request one through Aaron.

— Julian (2026-05-14)
