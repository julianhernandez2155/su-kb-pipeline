---
status: accepted
date: 2026-05-20
supersedes:
---

# 0009. MCP read-path filter: load-time filter at the corpus loader

## Context

[ADR-0007](0007-access-classification-v1.md) made the puller the canonical writer of `visibility_signal`. [ADR-0008](0008-space-classifier-tightening.md) tightened the space classifier so an unidentified-audience space's pages classify as `space_restricted`. Both fed the per-page frontmatter; neither enforced anything at the read path. Until Step 3, the chat / agentic surfaces still relied on the `(Test)` / `Summer Intern 2026` path-segment exclusion in `load_raw_corpus`, which would have leaked any restricted page that lacked the magic path segment.

The Phase 1.1 plan §"Step 3 — MCP / indexer enforcement" requires:

> Update `src/sukb/chat/` retrieval surfaces. `search` → `WHERE visibility_signal = 'no_read_restrictions_seen'`; `get_page` → reject any other value with a clean "not available"; `list_index` / `list_hubs` → filter listings; citation resolution → reject restricted citations.

Open design question: where exactly should the filter live?

## Decision

**Filter at the corpus-loader layer, in `load_raw_corpus` and `load_wiki_corpus`. The retrieval surfaces (`search`, `read_page`, `list_index`, `list_hubs`) inherit the filter without each needing its own check.**

Concretely:

- `load_raw_corpus(...)` filters to `visibility_signal == "no_read_restrictions_seen"` by default. `include_restricted=True` is the explicit escape hatch for admin / probe / puller paths. The PUBLIC value is a single canonical string — `accessible_to_sync_user` (legacy v2), `unknown`, blank, missing, or anything else is filtered.
- `load_wiki_corpus(..., allowed_raw_ids=...)` drops any hub whose `synthesizes` references a page not in the allowed set. Partial filtering (keeping the hub but redacting the source row) is unsafe — the hub body may contain citations, paraphrases, or quoted material from the restricted source. Drop the whole hub.
- `extract_citations(..., restricted_page_ids=...)` distinguishes restricted citations (surfaced as `(restricted — not available)`) from unresolved ones (`(unresolved)`). Both hide title + URL.
- `AgenticTools._source_pages_for_hub` provides defense-in-depth: any synthesizes ID not in the public-allowed set surfaces as `(not available)` regardless of whether the load-time gate dropped the hub. The model sees the same shape on restricted-source vs nonexistent-source entries — no way to distinguish.
- `AgenticTools._read_page` returns the SAME external "ERROR: no raw page with page_id=..." for restricted IDs as for genuinely nonexistent ones, so the model can't enumerate restricted IDs by probing. The eval TRACE summary annotates `(restricted)` for observability — never the text the model sees.

The retrieval surfaces (`search`, `read_page`, `list_index`, `list_hubs`) operate on the already-filtered lists. No per-surface visibility check; the chokepoint is the loader.

## Why load-time, not query-time

| Choice | Pros | Cons |
|---|---|---|
| **Load-time (chosen)** | Single chokepoint — every surface inherits. Surfaces stay focused on retrieval logic, not policy. Bug-hardening: a new surface added later can't forget to call the filter. | Filter runs once per process; visibility changes require restart. Doesn't matter for our deployment shape: the puller re-syncs, the chat process restarts, both are fine. |
| Query-time per surface | Defense in depth (multiple checks); could respond to visibility changes without restart. | Every new surface must remember to filter. Bug-prone — the very class of bug Step 3 is meant to eliminate. |

We layer both: load-time as the chokepoint, plus defense-in-depth at `_source_pages_for_hub` and `_read_page`'s response shaping. The DEFENSE layer cannot substitute for the chokepoint — if the loader returns a restricted page, the surfaces will happily serve it.

## What does the model see for restricted IDs

The external response for any restricted page must look IDENTICAL to a nonexistent page's response. This is non-negotiable: distinguishing the two creates an oracle for restricted-page enumeration. The trace summary distinguishes them for eval observability.

| Surface | Restricted page response | Nonexistent page response |
|---|---|---|
| `search` | (absent from hits) | (absent from hits) |
| `read_page(id)` text | `"ERROR: no raw page with page_id='X'"` | `"ERROR: no raw page with page_id='X'"` |
| `read_page(id)` summary | `"miss: raw X (restricted)"` | `"miss: raw X"` |
| `list_hubs` | (absent from list) | (absent from list) |
| `_source_pages_for_hub` | `{title: "(not available)", source_url: ""}` | `{title: "(not available)", source_url: ""}` |
| `extract_citations` | `{title: "(restricted — not available)", source_url: ""}` | `{title: "(unresolved)", source_url: ""}` |

The citation case is the one user-visible distinction — and it's a citation in the model's OUTPUT, not in the tool's response. The model has already committed to citing the page by the time we resolve. Surfacing the distinction to the operator (via the chat UI's citation panel) is correct — they need to know "you cited a restricted page" to fix the source.

## Verification

- 27 new tests in [tests/chat/test_step3_filtering.py](../../tests/chat/test_step3_filtering.py) cover all five surfaces + citation resolution + the canonical "Summer Intern fixture round-trip" from the plan's test matrix.
- 253 / 253 tests pass total.
- On the live ITSAI corpus: with `_is_test_page` path-segment exclusion disabled, the visibility filter alone correctly excludes the 3 Summer Intern pages (`1068171339`, `1069318154`, `1069350926`) and admits 31 clean pages. The path-segment exclusion is now genuinely redundant for `Summer Intern 2026` — follow-up ADR will remove it once the classifier has two clean weeks (per the plan).

## Consequences

**Positive:**

- Five retrieval surfaces enforce the policy via one load-time gate. New surfaces inherit automatically.
- "Forgot to filter" is no longer possible in the common case — it would require explicitly passing `include_restricted=True`, which is grep-able.
- Citation resolution gracefully degrades restricted IDs to a sentinel — the UI can flag them without leaking content.
- Real-corpus verification: the 3 Summer Intern pages do NOT appear via any surface, matching ADR-0007's intent end-to-end.

**Negative / trade-offs accepted:**

- Visibility changes require a process restart to take effect. The puller writes new frontmatter on every sync; the chat process loads at startup. Operationally fine for v1.5 ITSAI scope; revisit if/when we add a per-request visibility check for tenant-aware MCP.
- The `(Test)` / `Summer Intern 2026` path-segment exclusion still runs alongside the visibility filter. Belt-and-braces is intentional until follow-up ADR retires the `Summer Intern 2026` segment specifically (the `(Test)` segment stays — it's about content quality, not access).
- `load_raw_corpus` now reads frontmatter on every call. Already did (it parses frontmatter for `page_id`, `title`, etc.), so no measurable overhead.

## Alternatives considered

- **Query-time per-surface filtering.** Rejected — bug-prone, exactly the failure mode Step 3 must eliminate.
- **Maintain a separate `output/_views/public/` directory rebuilt on each sync.** Considered in ADR-0007's "Alternatives." Rejected as duplication; the load-time filter accomplishes the same outcome without copying bytes.
- **Reject restricted citations in the model OUTPUT (refuse to include `(restricted)` in the response).** Considered — would require post-processing the model's answer to strip restricted citations. Decided against: the operator-facing UI signal "you cited a restricted page" is more useful than silently dropping the citation, which would just make the model's answer look unfounded. The CONTENT of the restricted page is what we protect, not the existence of its `[[id]]`.

## References

- Plan: [docs/archive/phase-1.1-plan-2026-05-19.md](../archive/phase-1.1-plan-2026-05-19.md) §"Step 3 — MCP / indexer enforcement"
- Predecessors: [ADR-0007](0007-access-classification-v1.md), [ADR-0008](0008-space-classifier-tightening.md)
- Code:
  - [src/sukb/chat/query.py](../../src/sukb/chat/query.py) — `load_raw_corpus`, `load_wiki_corpus`, `extract_citations`
  - [src/sukb/chat/agentic_tools.py](../../src/sukb/chat/agentic_tools.py) — `AgenticTools` defense-in-depth
- Tests: [tests/chat/test_step3_filtering.py](../../tests/chat/test_step3_filtering.py)
