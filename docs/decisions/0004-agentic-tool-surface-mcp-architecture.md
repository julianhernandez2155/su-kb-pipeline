---
status: accepted
date: 2026-05-13
supersedes: [0003-rag-pipeline-mcp-architecture.md](0003-rag-pipeline-mcp-architecture.md)
---

# 0004. Agentic tool-surface MCP architecture

## Context

[ADR-0003](0003-rag-pipeline-mcp-architecture.md) scoped the production MCP server as a wrapper around an FTS5+RAG retrieval pipeline — one search tool, one-shot retrieval, classifier-filtered. After v1.5 Steps 1–5 and a Codex review pass, three pieces of evidence converged that this is the wrong shape:

1. **The raw-only baseline came in at 14 ✅ / 1 ⚠️ / 0 ❌** on 15 representative queries (see [eval-baseline-2026-05-13.md](../eval-baseline-2026-05-13.md)). That eval used full corpus in a cached system prompt — no retrieval pipeline, no FTS5, no classifier. The retrieval layer wasn't the bottleneck because there wasn't one. The wiki layer's purpose was reframed from "rescue bad retrieval" to "citation depth + canonical synthesis."

2. **Re-reading the MCP specification** — Resources are explicitly "application-driven" with hierarchical, browseable tree views. The protocol assumes Resources are a *structure* the calling model navigates, not opaque chunks behind a search tool. Tools are *verbs* the model composes (`list_hubs`, `read_page`, `search`), not a single black-box `query()`. The spec models the calling model as an *agent*, not as a final-answer generator over pre-fetched chunks.

3. **Anthropic tool-use docs** describe an agentic loop (`while stop_reason == "tool_use"`) where the model decides per-turn whether to call a tool. The model needs *orientation surfaces* (indexes, CLAUDE.md-style routing files) to make those decisions cheaply — otherwise it either dumps the whole corpus into context or fishes around with search calls. This matches how Claude Code itself navigates a workspace.

The triangulation point: a production Claude with our MCP should navigate the corpus the same way Claude Code navigates *this* workspace — reads top-level orientation, drills down, follows links, calls search only when the orientation didn't get it there.

## Decision

Production MCP server architecture (agentic tool-surface, not RAG pipeline):

1. **Storage layer** (unchanged from ADR-0003): the markdown corpus in `output/raw/` + `output/wiki/`.

2. **Resources** — MCP exposes the corpus tree as browseable Resources. The model can list, read, traverse. The layered orientation files we wrote during Step-5 prep are *load-bearing*, not decoration:
   - `output/CLAUDE.md` — agent rules for the whole corpus
   - `output/index.md` — global routing across spaces
   - `output/raw/<space>/index.md` — per-space routing
   - `output/wiki/index.md` — hub catalog with "when to use" annotations

3. **Tools** — small, composable verbs the model can call:
   - `read_index(path)` — read an orientation file
   - `list_hubs()` — enumerate wiki hubs with metadata (synthesizes, status, when-to-use)
   - `search(query, top_k=5)` — keyword search over corpus; FTS5 *if it exists* but not architecturally required
   - `read_page(page_id_or_slug)` — fetch a full raw page or wiki hub

4. **Generation layer** — agentic loop. The calling Claude reads orientation → decides which tool to call → reads the result → composes an answer with `[[page-id]]` citations. Tool-call traces are the artifact Aaron's team needs to validate the architecture.

5. **Classifier deferred or skipped.** Given the 14/15 baseline without classification, the Haiku-derived `audience`/`doc_type`/`tools`/`topics` fields aren't load-bearing. Decision to actually wire the classifier is deferred until Step 7 (agentic eval) tells us whether agentic navigation needs filtering at all.

6. **Wiki layer's job is reframed.** Hubs exist for *canonical synthesis* on cross-cutting topics — they make Q&A about "approved AI tools" cite per-tool depth automatically, instead of relying on Claude to assemble that synthesis ad-hoc from adjacent pages. Not rescue, canonization.

## Consequences

**Positive:**

- The production MCP build becomes mostly "wrap these four functions in Streamable HTTP + auth" — 80% of the architecture is prototyped in v1.5 (the four tools are scaffolded in [docs/next-phase-plan-v2.md §Step 7](../next-phase-plan-v2.md)). Shahaan's FastMCP work has a clear target shape.
- Orientation files (already written in v1.5 prep) earn their value as the navigation graph the model uses. Layered indexes generalize cleanly to future spaces (ITHELP, Maxwell).
- Wikilinks (`[[<page-id>]]`) become real graph edges the agentic model follows, not just citation decoration. The decisions in [ADR-0001](0001-page-id-prefixed-filenames.md) about page-ID-prefixed filenames pay off here.
- Step 7 of the v1.5 plan produces the actual production-shape eval: tool-call traces showing whether the model gets stuck, how many calls per query, whether it finds the wiki hubs when relevant. This is the data Aaron needs to greenlight the VM/MCP build.
- Cost shape becomes accurate to production: each tool call is a separate model turn. Estimated ~$0.05–0.20 per query vs. the ceiling test's $0.017 cached.

**Negative / trade-offs accepted:**

- Higher per-query cost than the cached-corpus ceiling — but that's the true production cost, not a regression.
- More moving parts than a single `search()` tool. Each tool needs its own implementation + tests. Mitigated: the tools are thin wrappers over the markdown corpus; ~150 LOC total is the estimate.
- The agentic loop can fail in modes RAG can't (model gets stuck, loops, misses the right tool). Step 7 is explicitly designed to surface these failure modes empirically *before* the production MCP is built.
- FTS5 is no longer the centerpiece. If Shahaan has Phase-B work assuming FTS5 as the retrieval primitive, this changes the framing: FTS5 becomes *one tool the agent can call*, not the whole retrieval pipeline.

## Alternatives considered

- **Stick with ADR-0003's RAG-pipeline shape.** Would have ignored the 14/15 baseline evidence and the MCP spec's actual model. Rejected.
- **Hybrid: RAG pipeline as default, agentic navigation as an opt-in mode.** Two architectures to build and test instead of one. Rejected unless Step 7 surfaces failure modes that motivate it.
- **Full agentic with no FTS5 ever.** Possible — `search()` can be a simple in-memory token match for v1. Defer FTS5 to v2 only if Step 7's traces show search is heavily used and slow. Accepted as the default starting point.

## Open questions to validate in Step 7

- Does Claude read the index files first, or skip to search? (If it skips, the orientation-file investment is wasted.)
- Does the wiki layer get discovered via `list_hubs()` and used canonically, or ignored in favor of raw-page search?
- How many tool calls per query on average? Are there queries where the model loops or never finds the right page?

References: [docs/next-phase-plan-v2.md](../next-phase-plan-v2.md) (the source-of-truth plan), [docs/eval-baseline-2026-05-13.md](../eval-baseline-2026-05-13.md) (the 14/15 evidence).
