---
status: superseded by [0007](0007-access-classification-v1.md)
date: 2026-05-19
supersedes:
---

# 0006. Visibility metadata is descriptive, not an enforcement boundary

## Context

Aaron Starr's 2026-05-18 stakeholder review asked how page restrictions interact with the ingestion pipeline ("if a page is restricted to certain people, we need to kind of have the AI not talk to that based on who you are"). For V1 we agreed to ingest public pages only and revisit access control when an OAuth 2.0 service account is provisioned.

Two API realities constrain what V1 can actually offer:

1. **Inherited restrictions aren't reliably returned by Confluence Cloud's REST API.** The direct `GET /wiki/rest/api/content/{id}/restriction/byOperation` endpoint reports restrictions set directly on a page but does *not* surface restrictions inherited from ancestors. Atlassian's own support note confirms this. Recovering inherited restrictions requires walking the ancestor chain or going through the UI's GraphQL surface — neither in V1 scope.
2. **REST authorization is driven by the calling user/token.** Our V1 puller authenticates with a PAT. Any field we write about "who can see this page" is at best a heuristic; the actual enforcement boundary is *what our sync user's PAT can fetch*. Pages our sync user cannot read simply do not enter the corpus.

Phase 1's metadata schema adds `visibility_signal`, `restriction_check`, and `restricted_to` so the schema doesn't need a migration when we add the active restriction check later. But these fields will look like access-control signals to anyone reading them.

## Decision

**Visibility-related frontmatter fields are descriptive best-effort metadata. They are not an enforcement boundary.** Downstream consumers (MCP server, eval harness, agent retrieval) MUST NOT treat them as authoritative for access control.

Concrete consequences for V1:

- All successfully fetched pages get `visibility_signal: accessible_to_sync_user` and `restriction_check: not_checked`.
- We do not call `/restriction/byOperation` in V1. The slots exist for when we do.
- We do not split the corpus into `raw/public/` vs `raw/internal/` folders. Premature without a real audience-separation model.
- We do not create a `quarantine/` folder for restricted pages. We cannot reliably discover restricted-but-inherited pages with our current API surface; building the folder before the discovery mechanism would create a misleading artifact.
- The access boundary in V1 is whichever Confluence pages the sync user's PAT can fetch — full stop.

## Consequences

**Positive:**

- Phase 1 ships without solving RBAC. The "public-only" posture Aaron approved is enforceable by token scope, not by markdown frontmatter.
- Schema slot exists for when OAuth/service account arrives. No re-ingest needed at that point.
- Honest about what the API actually gives us. Avoids overpromising "we know who can see this" to MCP consumers.
- Reports built on top of the corpus (staleness digests, tag inventories) don't need to special-case visibility-tagged pages in V1.

**Negative / trade-offs accepted:**

- Anyone reading a page's frontmatter could mistakenly treat `visibility_signal` as a permission gate. Mitigated by this ADR + a docstring in `frontmatter.py` calling the fields out as descriptive only.
- When restrictions later land, we'll need to backfill `restriction_check` for pages already on disk. Acceptable — re-ingest is idempotent and cheap.
- Pages restricted via inheritance that our PAT happens to access (e.g., ancestor restriction missed by the direct check) will be ingested without any "restricted" flag. The PAT-scoped access boundary is the safety net.

## Alternatives considered

- **Active per-page restriction check via `/restriction/byOperation` in V1.** Adds one API call per page per sync. Doesn't cover inherited restrictions. Defers no real value until we know what enforcement model Aaron wants. Rejected for V1.
- **GraphQL path for full restriction graph.** Out of scope for a public-only prototype. Reconsider when admin tier lands.
- **Folder split `raw/public/` vs `raw/internal/` immediately.** Codex flagged this as premature in G0 review — the audience-separation model doesn't exist yet, and the split would invent a partition we can't yet defend. Rejected.
- **Refuse to add the fields until enforcement is real.** Rejected — the schema slot is cheap; later backfill is the more disruptive path.

## References

- G0 / G1 design for Phase 1: [docs/phase-1-design-2026-05-19.md](../phase-1-design-2026-05-19.md)
- Aaron's restriction question + V1 public-only agreement: [docs/aaron-meeting-2026-05-18-followups.md](../aaron-meeting-2026-05-18-followups.md) §F-01
- Atlassian REST v2 page API: <https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/>
- Atlassian content restrictions API: <https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-restrictions/>
- Atlassian support note on inherited restrictions: <https://support.atlassian.com/confluence/kb/confluence-get-page-restrictions-api-doesnt-display-inherited-restrictions/>
