---
status: superseded by [0004-agentic-tool-surface-mcp-architecture.md](0004-agentic-tool-surface-mcp-architecture.md)
date: 2026-05-05
supersedes:
---

# 0003. RAG-pipeline MCP architecture

## Context

When the project was scoped, the planned production retrieval surface was a Model Context Protocol (MCP) server that wrapped a Retrieval-Augmented Generation pipeline. The mental model: corpus on disk → SQLite FTS5 index → MCP server's `search` tool runs FTS queries → returns matched chunks → Claude reads them and answers.

This shape mirrored Shahaan's Phase B design (FastMCP + httpx + SQLite FTS5 + Haiku classification) and was the working assumption for the v1.5 plan as originally written. The wiki layer was framed as "rescue raw-only failures" — synthesis hubs would patch up cross-cutting questions that single-page retrieval couldn't answer.

Two factors made this reasonable up front:

1. **RAG is the well-known shape.** Most production "ask my docs" systems are RAG pipelines. Tooling is mature.
2. **FTS5 is cheap and local.** No vector embeddings, no model dependency for retrieval itself, runs on a SU VM with no external state.

## Decision

Production MCP server architecture:

1. **Storage layer:** the markdown corpus produced by this prototype (`output/raw/` + `output/wiki/`).
2. **Index layer:** SQLite FTS5 index over the corpus. Built/refreshed by a sync job. Per-page rows; full-text query against `body` + frontmatter fields.
3. **Retrieval layer:** MCP server exposes a single `search(query, top_k)` tool. Returns top-k matched chunks with citations.
4. **Generation layer:** the calling Claude model reads search results, composes an answer with `[[page-id]]` citations.
5. **Classifier:** Haiku 4.5 fills `audience`, `doc_type`, `tools`, `topics` frontmatter fields during ingest. These become FTS5 filters for narrowed search.
6. **Wiki layer:** synthesizes cross-cutting topics. Same FTS5 index, with hub-status filter.

Implicit in this design: Claude does *one* tool call per question (or maybe two with refinement). Retrieval is a one-shot match. Orientation files (indexes, CLAUDE.md) are not architecturally load-bearing — they're nice-to-have documentation.

## Consequences

**Positive (as designed):**

- Conventional shape — Shahaan can build the MCP wrapper independently using FastMCP + httpx + sqlite3.
- Cheap retrieval — FTS5 query is milliseconds, no API cost for the retrieval call itself.
- Composable — same corpus could be fronted by other retrievers (vector store, hybrid) without changing storage.

**Negative (surfaced post-build, see ADR-0004):**

- Treats Claude as a one-shot answerer rather than an agent. Misses the MCP protocol's actual model of Resources (browseable tree) + Tools (composable verbs).
- Makes the wiki layer's job "rescue bad retrieval" rather than "provide canonical synthesis."
- Requires the classifier to do real work (filtering search space) — couples retrieval quality to classification quality.
- Doesn't exploit how the production Claude model would actually navigate a corpus: read orientation files first, follow wikilinks, call search only when needed.

## Alternatives considered (at the time)

- **Vector store (embeddings) instead of FTS5.** Rejected at scoping: more infrastructure, model dependency, no clear quality advantage on a 30-page corpus.
- **No index — pass full corpus in system prompt with caching.** Considered but assumed not to scale past a handful of spaces. (This turned out to be the *ceiling test* in Step 6 of the v1.5 plan, not a production option.)
- **Hybrid retrieval (FTS5 + reranker).** Deferred as a v2+ optimization.

---

**Why this ADR is superseded:** see [ADR-0004](0004-agentic-tool-surface-mcp-architecture.md). After the v1.5 Step-3 baseline came in at 14/15 raw-only (with no FTS5, no classifier, full corpus in cached prompt) and Codex review re-read the MCP spec carefully, it became clear that the production shape isn't a RAG pipeline — it's an agentic tool surface where retrieval is one verb among several and orientation files are load-bearing.
