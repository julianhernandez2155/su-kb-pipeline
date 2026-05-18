---
status: accepted
date: 2026-05-10
supersedes:
---

# 0002. Fallback-first ADF parsing

## Context

About 21% of pages in the SU `ITSAI` Confluence space use Atlassian Document Format (ADF) — Confluence's newer page-content representation — instead of the older "storage XML" format. The Confluence v2 API surfaces ADF pages with an `<ac:adf-extension>` wrapper containing two children:

- `<ac:adf-content>` — the canonical ADF body, encoded as a JSON document
- `<ac:adf-fallback>` — a storage-XML-shaped fallback that Atlassian produces from the ADF (intended for legacy consumers)

The ingest pipeline has to convert ADF pages to Markdown alongside storage-XML pages, ideally without duplicating the entire macro/walker pipeline. Two natural approaches:

1. **JSON-first.** Walk the ADF JSON tree natively. Need to implement handlers for every ADF node type (paragraph, heading, panel, expand, mention, status, etc.).
2. **Fallback-first.** Prefer `<ac:adf-fallback>` when present (it's storage-XML-shaped, so the existing macro registry and walker handle it for free). Fall back to JSON walking only when fallback is missing or empty.

In practice, Atlassian provides `<ac:adf-fallback>` for every ADF page we've seen — they treat it as the compatibility surface for legacy tooling. The fallback covers ~95% of the node types we care about; the JSON walker only matters for nodes Atlassian decided not to render in the fallback (rare modern node types).

## Decision

Use **fallback-first ADF parsing**:

1. Detect ADF via `page_uses_adf()` — looks for any `<ac:adf-*>` element in storage XML.
2. If `<ac:adf-fallback>` exists and is non-empty → walk it through the existing storage-XML pipeline. Macro handlers, wikilink resolution, attachment references all work unchanged.
3. If `<ac:adf-fallback>` is missing or empty → walk `<ac:adf-content>` JSON via a dedicated `render_adf()` function. The JSON walker reuses shared emitters (`render_callout`, `render_collapsible`) from the macro registry so panel/expand output is identical regardless of source format.
4. If `<ac:adf-content>` is missing or malformed JSON → **hard-fail to dead-letter**. Don't attempt heuristic recovery; the page lands in `output/conversion-failures/<space>/<page-id>.json` for human review.

## Consequences

**Positive:**

- The existing macro registry serves both source formats. Adding a new Confluence macro = one handler entry; it works for both storage-XML pages and ADF pages whose fallback contains the macro.
- Shared emitters mean a `panel` macro in a storage-XML page and an `panel` node in ADF produce identical Markdown. Citation discipline and downstream eval scoring don't have to special-case the source format.
- Hard-fail-to-dead-letter on bad JSON keeps the corpus clean — `output/raw/` never contains partial or recovered content. The strictness boundary is explicit: tolerate unknown macros, fail unparseable input.
- ~95% of ADF pages are handled by the simpler storage-XML path; only edge cases hit the JSON walker, so testing and maintenance cost is dominated by the simpler code path.

**Negative / trade-offs accepted:**

- We depend on Atlassian continuing to emit `<ac:adf-fallback>`. If they ever stop, the pipeline degrades to the JSON walker which has less coverage. Mitigation: the dead-letter path catches failures; we'd know immediately.
- Two parsing paths means two paths to maintain when adding handlers. We mitigate by sharing emitters but not the dispatch logic — adding a new ADF JSON node still requires a separate JSON walker case.

## Alternatives considered

- **JSON-only (skip the fallback entirely).** Cleaner — one code path — but requires implementing ~30 ADF node handlers up front. Most of those handlers would be reproducing logic the macro registry already has. Rejected: too much duplication for negligible robustness gain.
- **Convert ADF → storage XML at the API layer.** Would require either an Atlassian-provided conversion endpoint (doesn't exist) or our own reverse-mapping. Rejected: not worth the complexity, and Atlassian's fallback is already this conversion.
- **Accept ADF JSON as the canonical format; convert all storage-XML pages to ADF on ingest.** Inverts the problem. Rejected: storage XML is the older, more battle-tested format, and the macro registry naturally maps to it.
