---
status: accepted
date: 2026-05-20
supersedes:
---

# 0008. Space classifier: positive-ID via role:ANONYMOUS + allowlist fallback

## Context

[ADR-0007](0007-access-classification-v1.md) shipped Phase 1.1 access classification with an intentionally coarse space-audience heuristic: any non-empty `/spaces/{id}/permissions` response classified as `su_community`. The ADR called this out as "intentionally too coarse to distinguish a narrow allowlist within those records. Tightening the classifier requires reading the raw data and writing a 'restricted_space' heuristic; deferred to a future ADR."

A 2026-05-20 review pass flagged this as a Step 2 blocker for multi-space safety:

> for production public-only MCP, either:
> - positively identify the broad SU/community permission, or
> - mark space audience as unknown / filter out unless the space is manually allowlisted

The review is right. With Phase 1.1 Step 2 making the puller the canonical writer of access classifications, the per-sync space classification now feeds the MCP read-path filter (Step 3) for every space we onboard. A permissive `su_community` default would silently leak any non-ITSAI space whose 200 OK doesn't actually mean "broadly readable."

## Evidence

The ITSAI raw captured by Phase 1.1 Step 1 (probe run 2026-05-19) contains 225 paginated permission records. Among them:

```yaml
{"principal": {"type": "role", "id": "ANONYMOUS"},
 "operation":  {"key": "read", "targetType": "space"}}
```

In Atlassian Cloud, the `role:ANONYMOUS` principal marks a space as readable by anyone the site itself lets in. SU's tenant blocks unauthenticated access at the site level (the v2 endpoints require a valid PAT or OAuth token), so this marker effectively means "any authenticated SU user can read this space."

This is a clean positive-identification signal. We can test for its presence without enumerating SU's group GUIDs, and we can decline to classify any space that lacks it.

## Decision

**The space classifier is positive-identification by default; manual allowlist as fallback.**

Priority order in `sukb.ingest.spaces.classify_space_audience`:

1. **Operator allowlist override** — if `space_key` appears in
   `sync_config.yaml :: broadly_accessible_spaces`, return `su_community`.
   Use sparingly for spaces that lack the marker for legitimate reasons.
2. **Positive ID** — if the aggregated `/spaces/{id}/permissions` response
   contains a `role:ANONYMOUS` principal with `read/space` operation,
   return `su_community`.
3. **Otherwise** — return `unknown`.

And tightened page-level classifier in `sukb.ingest.access.classify_visibility`:

- `space.default_audience == "restricted_space"` → page is `space_restricted` (existing behavior).
- `space.default_audience == "unknown"` → **page is also `space_restricted`** (new).
- `space.default_audience == "skipped"` → page falls through to direct + ancestors (existing — operator hasn't refused us, the endpoint just isn't accessible).

The MCP filter (Step 3) treats `space_restricted` as restricted; pages in `unknown`-audience spaces are not queryable.

## Verification

- ITSAI continues to classify as `su_community` (the ANONYMOUS marker is present at permission record id `488144941`). The 34-page ITSAI corpus still classifies 31 / 3 / 0 / 0 / 0 (no_read / restricted_inherited / restricted_direct / space_restricted / unknown) post-tightening.
- Unit tests in [tests/ingest/test_access_classification.py](../../tests/ingest/test_access_classification.py) cover:
  - positive-ID present → `su_community`
  - positive-ID absent → `unknown`
  - allowlist override → `su_community`
  - ANONYMOUS on a different operation does not count
  - unknown space audience → page classifier returns `space_restricted`
  - empty / missing results → `unknown`

## Consequences

**Positive:**

- Onboarding a new space without explicit operator action defaults to "exclude from MCP" rather than "include." Safe-by-default for multi-space rollout.
- No reliance on SU-internal group GUIDs that may change or differ across spaces.
- Allowlist is a documented escape hatch when the positive-ID marker is missing for legitimate reasons; the operator must take an explicit action.

**Negative / trade-offs accepted:**

- A future SU-restricted space (e.g., HR, Legal) that legitimately should be in the corpus would default to excluded. Acceptable — Phase 1.1's MCP audience is "public ITSAI-style content," and onboarding any sensitive space deserves an explicit allowlist entry plus an ADR.
- The classifier still doesn't produce `restricted_space` — that requires a separate observed-data ADR. `unknown` covers the same MCP-side behavior for now.

## Alternatives considered

- **Keep ADR-0007's coarse heuristic (non-empty → `su_community`).** Rejected per the review. Multi-space safety requires a positive signal.
- **Group-ID allowlist** — enumerate SU's "all-authenticated-users" group IDs and check for them in the permissions. Rejected: requires probing every SU tenant and SU group taxonomy may evolve; the `role:ANONYMOUS` signal is stable Atlassian API surface.
- **Hard-fail (no allowlist override)** — reject any space without the ANONYMOUS marker outright. Rejected: removes operator agency. A research space with custom group permissions but a known SU-broad audience should still be onboardable by allowlist entry.
- **Per-page allowlist instead of per-space** — too fine-grained for v1. Per-space matches the deployment unit.

## References

- ADR-0007 (parent decision, defers this tightening): [0007-access-classification-v1.md](0007-access-classification-v1.md)
- Code: [src/sukb/ingest/spaces.py](../../src/sukb/ingest/spaces.py) — `classify_space_audience`, `has_anonymous_read_space`
- Code: [src/sukb/ingest/access.py](../../src/sukb/ingest/access.py) — `classify_visibility` (page-level)
- Config knob: [sync_config.yaml](../../sync_config.yaml) — `broadly_accessible_spaces`
- Atlassian space-permissions API: <https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space-permissions/>
