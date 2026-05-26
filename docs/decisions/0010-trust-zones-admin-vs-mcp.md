---
status: accepted
date: 2026-05-21
supersedes:
---

# 0010. Trust zones: admin web UI vs user-facing MCP retrieval

## Context

[ADR-0009](0009-mcp-read-path-filter.md) established a load-time chokepoint
in `load_raw_corpus` / `load_wiki_corpus` so the four MCP-shaped retrieval
surfaces (`search`, `read_page`, `list_index`, `list_hubs`) plus hub
`source_pages` only ever see pages whose `visibility_signal` is the
canonical public value. The chokepoint claim was "every user-facing
retrieval surface inherits the filter."

A 2026-05-21 external review (Codex) flagged that this is true for the
**MCP/chat retrieval surfaces**, but the current FastAPI server also
exposes routes used by the developer/admin UI that bypass the loader:

- `/api/pages` and `/api/pages/{page_id}` read pages directly out of
  `output/raw/`. They power the corpus browser tab that the developers /
  ITS team use to inspect ingest health, classifier output, frontmatter,
  and per-page diffs. They are not designed for end-user consumption.
- `/api/query/status` calls `load_wiki_corpus(config)` without
  `allowed_raw_ids` to compute a wiki-page count for the status panel.
  Returns no page bodies and no titles — just counts.
- The puller event surface (`/api/sync/*`) emits raw page metadata
  including titles of restricted pages while a sync is in progress.

These routes are operationally necessary for the developer/admin UI —
restricting them would require us to rebuild the ingest console on top
of the same MCP filter that intentionally hides content. But the
"chokepoint is airtight" story in ADR-0009 reads as though the filter
universally applies to every code path that touches the corpus.
It doesn't, and it shouldn't.

Without this ADR, the next person to extend the surface area
(developer, future intern, Shahaan) has no way to know which routes
must follow the public filter and which are intentionally privileged.
Worse: a future end-user MCP could be built by extending the FastAPI
layer and accidentally inherit the admin surface.

## Decision

**Distinguish two trust zones, document the boundary, and pin it in
code review:**

1. **Admin / developer surface** — the FastAPI web UI, the puller
   event stream, ingest status routes, the corpus-browser tab. May
   read raw content directly from `output/raw/` and may surface
   classifier/restriction metadata. Intended for ITS / EDA team
   operators inspecting the pipeline. Deployed inside the SU network
   behind operator authentication.

2. **User-facing MCP / chat surface** — `AgenticTools`,
   `_run_chat_stream`, `_run_agentic_stream`, `answer_query`, and any
   future MCP server wrapping `read_index` / `list_hubs` / `search` /
   `read_page`. MUST go through `load_raw_corpus` /
   `load_wiki_corpus` (no `include_restricted=True`) and MUST pass
   `restricted_page_ids` into `extract_citations`. Intended for end
   users; future production audience may be broader than internal
   operators (Aaron 1:1 to determine).

The boundary is enforced by convention + review, not by package
structure. The naming convention is:

- Functions/routes that intentionally bypass the filter take an
  explicit `include_restricted=True` argument, or live under
  `/api/pages*`, `/api/sync*`, `/api/query/status` (admin namespace).
- Functions/routes that serve end-user queries go through the
  filtered loader without `include_restricted=True`.

When a future surface is added, the reviewer asks: "is this called by
a real end user or only by the admin UI?" That question decides which
zone the new code belongs to.

## What this is NOT

- **Not a claim that the admin UI is "insecure."** It is a privileged
  console for ITS / EDA operators with legitimate access to
  Confluence content. The trust assumption is the same as the
  operator's Confluence account — they could read these pages
  directly in Confluence; the admin UI just makes the on-disk mirror
  inspectable.
- **Not a deferral of access controls.** The user-facing surface
  enforces ADR-0009 today, with regression coverage. This ADR pins
  *why* the admin surface looks different, so the asymmetry doesn't
  read as a bug.
- **Not a production-deployment plan.** If the production MCP audience
  expands beyond internal operators (open question in STATUS.md),
  the admin web UI may move behind tighter auth or be split into a
  separate process. That's a future decision; this ADR sets up the
  vocabulary for it.

## What changed in code alongside this ADR

The streaming chat paths in `sukb.web.server` had drifted from the
user-facing zone's contract. Three fixes landed in the same commit
as this ADR (with regression coverage in
[tests/web/test_chat_streaming_access.py](../../tests/web/test_chat_streaming_access.py)):

| Before | After | Why |
|---|---|---|
| `_run_chat_stream` called `load_wiki_corpus(config)` | passes `allowed_raw_ids=allowed_raw_ids` | A hub synthesizing a restricted page could enter the streaming raw+wiki prompt. Security-meaningful. |
| `_run_chat_stream` called `extract_citations(answer, raw_pages)` | passes `restricted_page_ids=...` | Restricted citations degraded to `(unresolved)` instead of `(restricted — not available)`. Operator signal weakness. |
| `_run_agentic_stream` called `extract_citations(full_answer, tools.raw_pages)` | passes `restricted_page_ids=tools._restricted_raw_ids` | Same operator-signal parity. Content was already filtered by `AgenticTools`, but the citation panel rendering was inconsistent with the non-streaming path. |

These bring the streaming user-facing routes into the same posture as
`answer_query` (the non-streaming user-facing entry point).

## Future-readiness notes (deferred, not part of this ADR's scope)

Two items were identified in the Codex review but deferred:

1. **Confluence restriction pagination audit.** The access manifest
   captures normalized `user_ids` and `group_ids` per page/ancestor,
   but the underlying API call uses `limit: 200`. Before treating
   manifest ACLs as RBAC-ready, confirm `/restriction/byOperation`
   either returns all principals or is paginated correctly. Today's
   ITSAI corpus is well under the limit; this is a per-user-RBAC
   precondition, not a v1.5 blocker.
2. **Effective-access evaluator.** Today's `classify_visibility` is a
   public-only function (does this page have any read restriction?).
   Per-user RBAC requires a separate evaluator: given user U's
   Confluence account ID + group memberships and page P's manifest
   entry, is U authorized? The classifier doesn't get replaced — it
   gets a sibling. Identity bridge (SSO → Confluence account ID +
   groups) is the upstream prerequisite. Gated on Aaron 1:1 about
   production MCP audience.

Both are tracked in STATUS.md "Open questions" / "Known future
improvements" rather than left implicit here, so they're discoverable
when the per-user conversation comes up.

## Alternatives considered

- **Force every route through `load_raw_corpus`.** Considered.
  Rejected because the corpus-browser tab's job IS to inspect raw
  on-disk state including restricted pages — that's how the operator
  verifies the classifier worked. Routing it through the public
  filter would break the developer console.
- **Split admin and end-user routes into separate FastAPI apps.**
  Considered — would make the boundary structural rather than
  conventional. Rejected for v1.5 because we have a single
  intern-built console and one deployment shape; splitting now is
  premature given Aaron hasn't decided on the production MCP audience.
  Worth revisiting if/when the production MCP ships separately.
- **Tag every route with a trust-zone marker (decorator or middleware).**
  Considered — concrete enforcement via code rather than convention.
  Deferred to a follow-up if a routing accident actually happens; the
  current surface is small enough that review catches it. Not worth
  the abstraction overhead today.

## Consequences

**Positive:**

- The ADR-0009 chokepoint claim is now scoped correctly: it applies
  to the user-facing zone, with named exceptions in the admin zone.
- A future contributor reading the codebase can answer "why does
  `/api/pages` not filter?" by reading this ADR rather than reverse-
  engineering intent.
- The streaming-path drift is closed; both streaming routes now
  match `answer_query`'s posture.

**Negative / trade-offs accepted:**

- The boundary is convention-enforced, not structurally enforced. A
  reviewer must catch any new route that mis-classifies its trust
  zone. Tolerable at current surface size; revisit if the FastAPI
  app grows.
- This ADR doesn't decide where the line will be in production
  deployment. That's the open "production MCP audience" question.

## References

- Predecessors: [ADR-0007](0007-access-classification-v1.md),
  [ADR-0008](0008-space-classifier-tightening.md),
  [ADR-0009](0009-mcp-read-path-filter.md)
- Code:
  - User-facing zone: [src/sukb/chat/query.py](../../src/sukb/chat/query.py),
    [src/sukb/chat/agentic_tools.py](../../src/sukb/chat/agentic_tools.py),
    [src/sukb/web/server.py](../../src/sukb/web/server.py)
    (`_run_chat_stream`, `_run_agentic_stream`)
  - Admin zone: [src/sukb/web/server.py](../../src/sukb/web/server.py)
    (`/api/pages`, `/api/pages/{page_id}`, `/api/query/status`,
    `/api/sync/*`)
- Tests: [tests/web/test_chat_streaming_access.py](../../tests/web/test_chat_streaming_access.py)
- Review: Codex review pass, 2026-05-21 — flagged streaming hub-filter
  drift + missing trust-zone documentation
