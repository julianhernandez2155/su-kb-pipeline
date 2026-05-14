---
title: v1.5 Baseline Eval — Raw-Only Mode
status: reviewed (Codex pass 2026-05-13)
date: 2026-05-13
project: kb-ingestion-internship
phase: Step 3 of next-phase-plan.md
mode: raw
model: claude-sonnet-4-6
queries_source: eval-queries.yaml (15 queries)
corpus: 29 ITSAI pages (test fixtures excluded)
run_artifact: ../../prototypes/confluence-to-md-v2/eval-runs/eval-baseline-raw-20260513T135909.json
---

# v1.5 Baseline Eval — Raw-Only Mode

Scoring of all 15 queries from [`eval-queries.yaml`](eval-queries.yaml) against the v1 ITSAI corpus in **raw-only** mode (no wiki hubs yet). First pass authored by Claude (Opus 4.7); second pass reviewed and adjusted by Codex.

The same set of queries will be re-run in `raw+wiki` mode in Step 6 to measure the wiki layer's lift on cross-cutting questions.

---

## Headline numbers (reviewed)

| Score | Count | % | Queries |
|---|---|---|---|
| ✅ Correct + complete | **14** | 93% | q01, q02, q04, q05, q06, q07, q08, q09, q10, q11, q12, q13, q14, q15 |
| ⚠️ Partial            | **1**  | 7%  | q03 |
| ❌ Wrong / missing    | **0**  | 0%  | — |

> **Reviewer note (Codex, 2026-05-13):** The first pass marked q04, q12, q13 as ⚠️ because they missed page_ids the eval listed. On re-read, all three answers were materially correct and the missed citations were optional context rather than required content. Final score upgrades these three to ✅. **q03 stays ⚠️** — the answer is correct but cites only the approved-tools master page, which is exactly the citation-depth gap the wiki layer is meant to fix.

**Wiki-benefit flag (3 queries flagged `expected_to_benefit_from_wiki: true`):**

| ID | Reviewed score | Hypothesis for Step 6 |
|---|---|---|
| q03 | ⚠️ | Wiki hub on approved tools should add per-tool FAQ depth to the citation trail |
| q04 | ✅ | Already strong in raw — wiki should make the comparison more canonical, not rescue |
| q11 | ✅ | Raw-only handled it cleanly — wiki adds stability/canonicality, not correctness |

---

## Cost & latency

| Metric | Value |
|---|---|
| Total queries | 15 |
| **Total cost** | **$0.3891** |
| Cache prime (q01) | $0.1468 |
| Avg cost, queries 2–15 | $0.0173 |
| Avg latency | ~13.5 s (range 3–58 s) |
| Outlier (q02 latency) | 58.2 s — looked like a cache-miss/rate-limit blip; q02's cost ($0.0137) confirms cache *was* still hit, so this is a server-side slowdown, not a re-prime |

**Implication for ramp:** at $0.017/query in cached mode, a 100-query eval would cost ~$1.85. Aaron's pre-approval ceiling of ~$5 covers this with room.

---

## Per-query results

Sessions are saved to `output/query-sessions/` and visible in the Query-tab sidebar. The `session_id` column lets you click into any saved chat in the UI.

| ID | Type | Score | Cited (real titles) | Why (if not ✅) | Session |
|---|---|---|---|---|---|
| q01 | factual | ✅ | Claude FAQ, Approved Tools | — | `20260513T175921-096236` |
| q02 | factual | ✅ | Claude FAQ | — | `20260513T180020-e0be65` |
| q03 | synthesis | ⚠️ | Approved Tools *(only)* | Cited the single master list page; never opened the per-tool FAQs (Claude FAQ, Copilot FAQ, Gemini FAQ). Answer is functionally complete (lists all 8 approved tools) but the citation trail is thin — a compliance reviewer following the answer can't reach per-tool data-handling details. **Wiki should help.** | `20260513T180026-8b5235` |
| q04 | synthesis | ✅ | Creative AI Workflows, Research Assistant, Claude FAQ, Study Project, Smart Study Gemini, Gemini @ SU, Approved Tools | Hit 2/4 expected; missed Copilot/Gemini FAQs but pulled in **arguably better pages** (Creative AI Workflows is a de-facto comparison page). Answer is materially useful. Wiki's job here is to make this comparison canonical, not rescue. | `20260513T180041-ba5a85` |
| q05 | where-do-i | ✅ | AI @ SU, Claude Enterprise @ SU | — | `20260513T180044-374562` |
| q06 | where-do-i | ✅ | Purchase Claude Code, Claude Code Setup | — | `20260513T180057-01b598` |
| q07 | policy | ✅ | Claude FAQ | — | `20260513T180103-ead044` |
| q08 | policy | ✅ | Claude FAQ | — | `20260513T180116-d0deb9` |
| q09 | factual | ✅ | mentorAI @ SU, AI @ SU, mentorAI Tools, mentorAI Settings, Claude FAQ | Hit both expected; extras are good context. | `20260513T180128-08d7d3` |
| q10 | how-to | ✅ | mentorAI @ SU, mentorAI Creating, mentorAI Settings | — | `20260513T180139-e85002` |
| q11 | synthesis | ✅ | Local MCP, Requesting Connector, Connect M365, SharePoint Files | Hit both expected. Excellent multi-page synthesis in raw-only mode. **Counter-example to the wiki hypothesis for this query** — raw-only already handles it. | `20260513T180157-5d371d` |
| q12 | how-to | ✅ | Connect M365 *(only)* | Question asks how to connect M365. Answered correctly from the dedicated page. The broader connector-request page is optional context. | `20260513T180205-e18189` |
| q13 | how-to | ✅ | How to use NotebookLM *(only)* | Question asks if NotebookLM is available + what it can do. The NotebookLM page fully answers that. Gemini-at-SU framing is nice, not required. | `20260513T180216-618183` |
| q14 | factual | ✅ | Claude FAQ, Copilot FAQ, Gemini FAQ | Hit expected; chose to give a cross-platform answer voluntarily, which strengthens the answer. | `20260513T180224-74f166` |
| q15 | where-do-i | ✅ | Study Project, Career Project, Meeting Summaries, Research Assistant, Drafting Emails, Creative AI Workflows, Claude Enterprise | Hit **5/5** expected. | `20260513T180233-109b43` |

---

## Observations

### What raw-only does well

- **Single-source factual queries** are nearly perfect (q01, q02, q05, q07, q08, q14). When the answer lives mostly in one page, Claude finds it and cites cleanly.
- **Multi-page how-to with one anchor page** also works (q06 Claude Code, q10 mentorAI mentor creation, q11 MCP). Raw-only synthesis is more capable than the plan assumed.
- **List queries** (q15 — "where are example uses") nail it when the corpus is well-organized into a clear sub-tree.

### Where raw-only falls short

Two failure modes show up consistently:

1. **Picks one master page, skips the per-feature pages** (q03 hit only Approved-Tools, q12 hit only Connect-M365). The answer is *functionally* complete but loses the citation depth that a power user or compliance reviewer would want.
2. **Adjacent-page misses on cross-cutting topics** (q04 missed Copilot/Gemini FAQs but picked up Creative Workflows + Smart Study Gemini). The answer is good, but the eval's expected citations weren't matched. This is partly an eval-set authorship question: are *both* the Approved-Tools and Per-Tool FAQ truly required, or is Approved-Tools enough?

### Reframed: what the wiki layer is actually for

The reviewed baseline (14 ✅ / 1 ⚠️) means raw-only is **already strong**. The wiki layer's purpose is therefore *not* to rescue bad answers. Codex's framing for Step 4 onward:

> "The wiki layer's purpose is not to fix broad raw-only failure; it is to improve **citation depth**, **canonical synthesis**, and **stable answers** for cross-cutting questions. Prioritize hub candidates that make q03 and q04-style answers more authoritative, not hubs that duplicate already-good how-to pages."

Concretely:
- A wiki hub for **Approved AI Tools for University Data** would have made q03 (the one remaining ⚠️) cite per-tool FAQ depth automatically, *and* make q14's voluntarily cross-platform answer canonical instead of accidental.
- A **Claude/Copilot/Gemini comparison** hub would make q04 the canonical answer instead of one assembled ad-hoc from 7 adjacent pages.
- An **MCP/Connectors** hub is lower urgency — raw already handles q11 — but valuable as a stable, demoable canonical artifact for Aaron.

### Implications for Step 4 (wiki proposals)

Ranked by expected leverage, given the reviewed baseline:

1. **Approved AI Tools for University Data** — highest priority. Closes the one ⚠️ and makes cross-platform policy answers canonical.
2. **Claude / Copilot / Gemini for Academic Work** — medium priority. Raw answers it, but the wiki version becomes the canonical decision artifact.
3. **MCP and Connectors at Syracuse** — lower urgency on the eval signal, but a clean demo hub.

Codex's guidance: **fewer, sharper hubs**. Don't pad to a number; let the proposal pass surface candidates and accept only those that genuinely improve citation depth or canonical synthesis.

---

## Next

- [x] **Human review pass** — Codex 2026-05-13, flipped q04/q12/q13 ✅, kept q03 ⚠️.
- [ ] **Step 4** — Karpathy-style proposal pass over 29 pages (target: `wiki-proposals-2026-05-13.md`). Treat raw-only as strong; prioritize hubs that *improve* canonical synthesis, not rescue failures.
- [ ] **Step 5** — seed up to 3 reviewed wiki hubs in `output/wiki/`. Fewer + sharper > more + diluted.
- [ ] **Step 6** — re-run this eval in `raw+wiki` mode; diff results; write `v1.5-results.md`.

The reproducer is `python scripts/run_eval.py --mode raw` against a running uvicorn on `http://127.0.0.1:8765`. Output JSON and 15 saved sessions are the canonical artifacts.
