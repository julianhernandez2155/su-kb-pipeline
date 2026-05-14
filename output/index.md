# SU AI Knowledge Base — Index

The corpus that powers SU's AI-assisted Q&A surface. Mirrors public-at-SU Confluence content plus an LLM-drafted, human-reviewed synthesis layer.

## How to use this index

If you're a Claude model navigating this corpus to answer a user question:

1. **Cross-cutting question** (policy comparison, tool selection, "what's enabled at SU") → check `wiki/index.md` first. A hub may answer it directly with citations.
2. **Tool-specific or how-to question** → go to the relevant space below, then its `index.md` for routing.
3. **Look up a specific page by ID** → it's at `raw/<category>/<space>/.../<page-id> - <title>.md`.

Rules for what to cite and how live in [`CLAUDE.md`](CLAUDE.md).

## Spaces present

| Space | Content | Pages | Index |
|---|---|---|---|
| **Artificial Intelligence (AI)** | All SU-supported AI tools: Claude, Copilot, Gemini, mentorAI (Clementine), NotebookLM. Approved-tools policy, data classification, MCP and connectors, Claude Code setup, example use cases. | 29 | [`raw/knowledge-bases/Artificial Intelligence (AI)/index.md`](raw/knowledge-bases/Artificial%20Intelligence%20(AI)/index.md) |

Future spaces (ITHELP, Maxwell, college- and school-specific KBs) will land as additional rows. Each space gets its own `index.md` once added.

## Wiki synthesis layer

Reviewed cross-cutting hubs that synthesize ≥3 raw pages each. See [`wiki/index.md`](wiki/index.md) for the full map. Quick pointers:

- **Approved AI tools — data policy & comparison** → `wiki/approved-ai-tools-for-university-data.md`
- **Claude at Syracuse — product surface map** → `wiki/claude-at-syracuse-product-surface-map.md`

## What lives outside the queryable corpus

- `raw/.meta/` — sync state per space (not content; do not surface to users)
- `conversion-failures/` — dead-letter pages from past pulls (not content; ITS reviews these)
- `query-sessions/` — saved Query-tab chats from eval runs (eval artifacts, not corpus)
- `attachments/` — files referenced by pages (PDFs, scripts, images); accessible via `[filename](attachments/<page-id>/<file>)` links inside pages
