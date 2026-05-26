---
title: v1.5 Phase Plan — Updated (post-architectural-pivot)
status: ready to execute (in a fresh chat)
date: 2026-05-14
project: kb-ingestion-internship
supersedes: next-phase-plan.md (Steps 1–5 complete; this doc reframes 6+ and adds 7)
prerequisites: Steps 1–5 done — eval queries, chat interface, baseline eval, hub proposals, 2 reviewed wiki hubs
---

# v1.5 Phase Plan — v2

This document supersedes [`next-phase-plan.md`](next-phase-plan.md) after Steps 1–5 completed and the architecture matured. Read it cold and start executing.

---

## How to start the next chat

Paste this as the first message of the new chat:

> Read `SU_AI_Intern/research/kb-ingestion-project/v1-tool-brief.md`, `wiki-operating-model.md`, `eval-baseline-2026-05-13.md`, `archive/wiki-proposals-2026-05-13.md`, and `next-phase-plan-v2.md` in that order. Then execute the plan starting at the "Pre-Step-6: orientation files" task. Stop after each step for review.

---

## TL;DR — what changed since v1 of the plan

The original plan assumed the production architecture would be a FTS5+RAG MCP server. After a Codex review pass and a deeper look at how MCP actually works:

- **Production MCP is an agentic tool-surface, not a RAG pipeline.** The MCP spec treats Resources as hierarchical and browseable; the production Claude model navigates them iteratively, the same way Claude Code navigates a workspace. FTS5 is *one tool* the model can call, not the whole story.
- **Layered orientation files (`CLAUDE.md` + indexes) are the load-bearing structure.** Without them, Claude has to either dump all 29 pages into context or make many search calls fishing for the right page. With them, Claude orients → drills down → answers. Triangulated against MCP spec (Resources tree-browseable), Anthropic tool-use docs ("only call the tool when needed"), and observable Claude Code behavior.
- **The wiki layer's job changed.** It was framed as "rescue raw-only failures." After the reviewed baseline came in at 14 ✅ / 1 ⚠️ / 0 ❌, raw-only is already strong. The wiki layer's real job is **citation depth, canonical synthesis, and stable answers for cross-cutting questions** — not rescue.
- **A new Step 7** tests this architecture empirically: build a small tool-use simulator (`read_resource`, `list_hubs`, `search`, `read_page`) and run the 15 eval queries through agentic navigation. This is the data Aaron needs *before* anyone builds the production MCP server on a VM.

---

## Current state (Steps 1–5 complete)

| Component | Status | Artifact |
|---|---|---|
| Eval query set (15 queries, 3 wiki-flagged) | ✅ | [`eval-queries.yaml`](eval-queries.yaml) |
| Chat interface backend (`/api/query`) | ✅ | `prototypes/.../kb_ingest/api/query.py` |
| Chat tab UI + session save/load | ✅ | `prototypes/.../frontend/index.html`, `kb_ingest/api/sessions.py` |
| Baseline raw-only eval | ✅ **14 ✅ / 1 ⚠️ / 0 ❌** | [`eval-baseline-2026-05-13.md`](eval-baseline-2026-05-13.md), [`eval-runs/eval-baseline-raw-20260513T135909.json`](../../prototypes/confluence-to-md-v2/eval-runs/eval-baseline-raw-20260513T135909.json) |
| Karpathy proposal pass | ✅ 2 candidates, 6 rejected | [`archive/wiki-proposals-2026-05-13.md`](archive/wiki-proposals-2026-05-13.md) |
| Wiki hubs (Step 5) | ✅ both `status: reviewed` | `prototypes/.../output/wiki/approved-ai-tools-for-university-data.md`, `claude-at-syracuse-product-surface-map.md` |
| Test suite | ✅ 257/257 green | `prototypes/.../tests/` |
| Saved query sessions (eval traces) | ✅ 15 sessions | `prototypes/.../output/query-sessions/` |

**Total cost incurred:** ~$0.39 in legitimate end-user-simulation queries + ~$2.76 in project-internal LLM work that should have been done in-session (the run_proposals.py + draft_hubs.py runs — see Cost Discipline section below).

---

## The architectural pivot, explained

The original plan modeled production retrieval as: *MCP server does FTS5 search → returns matches → Claude reads them.* That's a RAG pipeline wrapped in MCP.

The correct mental model is: *MCP server exposes Resources (the file tree, including indexes) and Tools (search, read_page). The production Claude model navigates the corpus the same way Claude Code navigates this workspace — reads orientation files, follows wikilinks, calls search when needed.*

Verified against:
- **MCP specification:** Resources are explicitly "application-driven" with hierarchical tree views; the protocol assumes browseable structures.
- **Anthropic tool-use docs:** The agentic loop pattern (`while stop_reason == "tool_use"`) with "only call the tool when needed" requires Claude to make routing decisions, which requires orientation surfaces to make those decisions cheap.
- **Claude Code itself:** I (the agent in this session) navigate Julian's workspace by reading top-level `CLAUDE.md` first, then drilling down. Production Claude with our MCP should work the same way.

Consequence: the wiki/raw split + page-ID-prefixed filenames + `[[pid]]` wikilinks + `synthesizes:` lists we built are **the navigation graph**, not decoration. They earn their value only if we also build the orientation surfaces (indexes + CLAUDE.md) that let the model use the graph.

---

## Cost discipline rule

Two different billing surfaces, two different rules:

- **Claude Code subscription (this session):** covers everything we do here — file edits, planning, in-session synthesis, code review, drafting markdown. **No per-call cost.**
- **`ANTHROPIC_API_KEY` in `.env`:** pay-per-token. Use *only* for end-user simulation — anything that tests "what does a student or faculty member see when they ask Claude a question with our MCP enabled."

**Use the API for:** `/api/query` endpoint chats, `run_eval.py`, the agentic tool-use simulator in Step 7. These are the production architecture under test.

**Don't use the API for:** drafting hubs, proposing candidates, writing analysis, reviewing eval results, refactoring scripts. All of that is project-internal LLM work — the Claude Code session covers it for free.

---

## Pre-Step-6: orientation files (do this first)

Four files. All in-session, no API calls. ~30 minutes total.

| File | Purpose | Style |
|---|---|---|
| `prototypes/confluence-to-md-v2/output/CLAUDE.md` | Agent rules for anyone (human or LLM) working with the corpus: raw is immutable mirror, wiki has citation discipline, status field convention, how to add a hub. | Short — under 100 lines. Pattern after `enterprise-ai-kb/CLAUDE.md`. |
| `prototypes/confluence-to-md-v2/output/index.md` | Global map of the corpus. Spaces present, what each one covers, pointers to space indexes and to wiki/. | Tiny — under 50 lines. Lists spaces with one-liners. |
| `prototypes/confluence-to-md-v2/output/raw/knowledge-bases/Artificial Intelligence (AI)/index.md` | Space-level routing: subcategories (Claude/, Copilot/, Gemini/, Clementine Platform/, AI - General Information/), one-line purpose for each, page counts, pointer to relevant wiki hubs. | 50–80 lines. Could be auto-generated later. |
| `prototypes/confluence-to-md-v2/output/wiki/index.md` | Wiki hub map: which hubs exist, when each applies, what each synthesizes, status. | 30–50 lines. |

**Discipline:** each file is substantive (matchable text describing relationships), not navigation stubs. The wiki/space indexes should mention concrete question types they help answer — that's what makes them search-matchable AND useful for the agentic model.

**Update `load_wiki_corpus`** in `kb_ingest/api/query.py` if needed to ensure `wiki/index.md` is treated as a wiki page (or as a special "index" type). Update tests.

---

## Step 6 — Ceiling eval (raw+wiki, full corpus in context)

Re-run all 15 queries from `eval-queries.yaml` in `raw+wiki` mode. With orientation files in place, this measures the **upper bound**: what's the best answer quality if Claude has access to everything (raw + hubs + indexes) in a single prompt.

**Command:**
```powershell
python scripts/run_eval.py --mode raw+wiki --server http://127.0.0.1:8765
```

(Server must be running; SDK + API key in `.env`.)

**Expected cost:** ~$0.35 (prime $0.15 + 14 × $0.014).

**Output:** `research/kb-ingestion-project/eval-wiki-2026-MM-DD.md` (drafted in-session by reading the run JSON and scoring against the baseline format).

**Acceptance:**
- All 15 queries scored (✅ / ⚠️ / ❌)
- Diff vs. baseline highlighted — specifically q03 (the one baseline ⚠️) and the two cross-cutting hubs' addressed queries (q03, q04, q11)
- Headline: did the wiki layer move anything from ⚠️/❌ to ✅, or strengthen citation depth on already-✅ queries?

---

## Step 7 — Agentic tool-use simulator (the production-shape test)

**New step.** This is what makes the v1.5 deliverable map onto the production MCP architecture.

### What to build

`prototypes/confluence-to-md-v2/scripts/run_agentic_eval.py` — a script that:

1. Defines four tools (matching what an MCP server would expose):

| Tool | Purpose | Input | Output |
|---|---|---|---|
| `read_index` | Read an orientation file by relative path | `path: str` (one of: `CLAUDE.md`, `index.md`, space index, `wiki/index.md`) | full markdown content |
| `list_hubs` | List wiki hubs with metadata | none | `[{title, slug, synthesizes, status, when_to_use}]` |
| `search` | Keyword search over the corpus (raw + wiki) | `query: str, top_k: int = 5` | `[{page_id_or_slug, title, snippet}]` — simple substring or tokenization match is fine for v1 |
| `read_page` | Read a full raw page or wiki hub | `page_id` (raw) or `slug` (wiki) | full markdown + frontmatter |

2. For each of the 15 queries:
   - Initialize conversation with a system prompt explaining the SU KB shape + tools
   - Send the query
   - Loop on `stop_reason == "tool_use"` until `end_turn`
   - Capture: final answer, **full tool-call trace** (this is the key new artifact), citations, total cost, latency, total tool calls
3. Save each as a chat session via `/api/query/sessions` (extend the schema to include tool_calls if needed) so it shows in the UI sidebar
4. Write `research/kb-ingestion-project/eval-agentic-2026-MM-DD.md`

### Why this matters

The tool-call trace is the data Aaron actually needs. It answers:
- Does Claude read the index first, or skip to search?
- Does the wiki layer get found via `list_hubs` and used canonically, or ignored?
- How many tool calls per query on average?
- Are there queries where Claude gets stuck in a loop / never finds the right page?

If this lands well, the production MCP work becomes "wrap these 4 functions in Streamable HTTP + OAuth/JWT" — 80% of the architecture is already prototyped.

### Expected cost & shape

Per query: 3–6 tool calls × roughly 10–20k tokens of accumulating context. Estimate $0.05–$0.20 per query, total $1.50–$3.00 for the 15.

Significantly higher than Step 6 because each tool call is a separate model call. This is the real production cost shape — worth measuring.

### Acceptance

- All 15 queries run with full tool-call trace captured
- Scored on the same ✅/⚠️/❌ rubric
- A short trace analysis section: tool-call patterns, which tools were most useful, where Claude got stuck
- 3-column comparison in the writeup: baseline / ceiling / agentic

---

## Step 8 — v1.5 writeup for Aaron

`research/kb-ingestion-project/v1.5-results.md` — the Aaron-facing deliverable. Synthesizes the three eval runs.

**Structure:**
```markdown
# v1.5 Results — Eval Across 3 Retrieval Architectures

## Setup
- 29 raw ITSAI pages + 2 wiki hubs + 4 orientation files
- 15-query eval set
- 3 retrieval modes tested

## Headline
| Mode | ✅ | ⚠️ | ❌ | Total cost | Per-query avg |
|---|---|---|---|---|---|
| Baseline (raw only, full corpus) | 14 | 1 | 0 | $0.39 | $0.026 |
| Ceiling (raw+wiki, full corpus)  | TBD | TBD | TBD | $0.35 | $0.023 |
| Agentic (MCP-shape tool calls)   | TBD | TBD | TBD | $1.50–3.00 | $0.10–0.20 |

## Where each mode wins / loses
[per-query diff table]

## Tool-call trace analysis (agentic mode)
[which tools used, which patterns succeeded, where Claude struggled]

## What this means for the production MCP
- The architecture should be agentic tool-surface, not RAG-pipeline-in-MCP
- The orientation files are load-bearing
- The wiki layer earns its value through canonical synthesis, not rescue
- VM/MCP build is 80% prototyped — main remaining work is auth + transport, not retrieval logic

## Open questions for Aaron 1:1
[items from below]
```

In-session drafting. No API.

---

## Open questions for the Aaron 1:1

Restated and updated from the original brief:

1. **The "Answers" Confluence space** (Data Center site, no category) — prior art or defunct?
2. **MCP rollout audience** — internal ITS/EDA only, or broader SU users? Defines OAuth-flow urgency.
3. **Attachment policy** — confirm v1's "preserve as raw refs" is fine; PDF/DOCX extraction is post-v1.5.
4. **Sync infrastructure** — where does the sync job run? SU VM, Microsoft Fabric, Azure Function? Phase B assumed SU VM.
5. **Filename scheme** — page-ID prefix confirm/override (currently used).
6. **Eval set authorship** — should we seed Step 9+ evals from real Confluence search logs if available?
7. **Classifier budget** — original plan asked about Haiku 4.5 for `audience`/`doc_type` fields; given raw-only's strong baseline, **is the classifier still worth $5/sweep, or do we defer indefinitely?**
8. **(NEW) Architecture confirmation** — agentic tool-surface MCP vs. RAG-pipeline MCP. Step 7's results will inform this; Aaron should weigh in before VM build.
9. **(NEW) Layered-index pattern** — confirm 4-file orientation structure is the standard for future spaces (ITHELP, Maxwell, etc.).

---

## Out of scope (still, with updated targets)

| Component | Defer to | Note |
|---|---|---|
| Production MCP server (Streamable HTTP + OAuth/JWT) | v3 | Architecture validated in Step 7; remaining work is transport + auth |
| Haiku classifier (audience/doc_type) | v1.1 *or skip* | Decide after Step 7 — may not be worth it if agentic navigation is strong enough |
| FTS5 indexer as separate component | Probably skip | Built into Step 7's `search` tool; doesn't need to be SQLite-FTS5 specifically |
| Additional Confluence spaces | post-v3 | Architecture supports it now; gated by config |
| Wiki lint loop | post-v3 (>10 wiki pages) | |
| Real search-log eval queries | post-v3 | Need ITS access to Confluence search logs |
| Space-index auto-generation | post-v1.5 | Nice-to-have for when ITHELP / other spaces land |

---

## Acceptance criteria for the v1.5 phase

The phase is done when:

- [ ] 4 orientation files in place and meaningful
- [ ] Step 6 (ceiling eval) results in `eval-wiki-*.md` with all 15 scored
- [ ] Step 7 (agentic simulator) results in `eval-agentic-*.md` with full tool-call traces
- [ ] `v1.5-results.md` ready for Aaron — three-column comparison, trace analysis, architecture recommendation
- [ ] No pytest regressions (currently 110 green; new tests for any new code)
- [ ] Aaron can be walked through the demo in under 10 minutes, with the production-architecture story landing clearly

---

## Why this phase, in one paragraph (updated)

The v1 build proved we can convert Confluence cleanly. The v1.5 baseline proved the corpus already answers questions well in a ceiling test. What the project actually needs to know before the VM/MCP investment is: **does the production architecture (agentic Claude + MCP tool surface + layered indexes) hold up against the ceiling, at acceptable cost?** That's what Step 7 measures. If it lands, the path to production is short and Aaron has a defensible case. If it doesn't, we learn specifically where the architecture breaks before sunk cost grows.
