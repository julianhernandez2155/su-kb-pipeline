---
status: accepted
date: 2026-05-19
supersedes: 0006
---

# 0007. Access classification v1 — descriptive metadata, computed from direct + ancestor + space layers

## Context

ADR-0006 (2026-05-19, same day) declared visibility frontmatter fields descriptive-only and explicitly punted on calling `/restriction/byOperation`. That posture was driven by an Atlassian support note saying the endpoint doesn't surface inherited restrictions — true, but recoverable by walking the ancestor chain and checking each ancestor's direct restrictions. The 2026-05-19 probe captured in `docs/access-metadata-plan-2026-05-19.md` confirmed this: the Summer Intern 2026 folder (`1069121551`) carries direct read restrictions, and its child pages would be left as `accessible_to_sync_user` (false-clean) under ADR-0006's posture.

Aaron's 2026-05-18 stakeholder agreement was "public pages only for V1." That isn't actually enforced by the puller's PAT — the PAT happens to belong to a user who's on the Summer Intern folder's allowlist, so the sync user can read those pages and the corpus would silently include them under ADR-0006.

Phase 1.1 needs to:

1. Compute an honest `visibility_signal` for every page (no more universal `accessible_to_sync_user`).
2. Walk direct + ancestor + space layers; report which layers actually completed.
3. Surface restriction-source IDs in frontmatter so the MCP can filter cheaply.
4. Stop short of per-user RBAC — that's a separate, post-OAuth project.
5. Be reversible without re-ingesting bodies — frontmatter rewrite only.

Planning doc: [docs/phase-1.1-plan-2026-05-19.md](../phase-1.1-plan-2026-05-19.md).
Predecessor: [docs/access-metadata-plan-2026-05-19.md](../access-metadata-plan-2026-05-19.md).

## Decision

**Phase 1.1 classifies each page into one of five `visibility_signal` values, computed from three layers (direct restrictions, ancestor-chain restrictions, space audience), and writes the result to frontmatter alongside a per-page access manifest.**

The classifier is descriptive (drives MCP filtering at read path; not the security boundary). The security boundary is still the sync user's PAT scope, same as ADR-0006. What this ADR adds: a *second* layer of defense at the MCP retrieval surface, so a future PAT change that broadens access can't accidentally leak previously-restricted pages without re-classification.

### Vocabulary

`visibility_signal`:

| Value | Meaning |
|---|---|
| `no_read_restrictions_seen` | Direct + ancestor walk completed, no `read` restrictions found. Only this value is queryable by the v1 MCP. |
| `restricted_direct` | Page has a non-empty `read` restriction directly on itself. |
| `restricted_inherited` | At least one ancestor (page or folder) has a `read` restriction. |
| `space_restricted` | Space-level audience classified as `restricted_space`. Reserved — not produced in Phase 1.1 by the conservative `su_community` heuristic. |
| `unknown` | Direct or ancestor check failed (403, network, shape mismatch). Treated as restricted by the MCP. |

`restriction_check`: an array of layer names in fetch order — `["direct", "ancestors", "space"]` when all three succeeded; `space` is omitted if the endpoint 403'd. Empty array means nothing was checked (treat as `unknown`).

`restriction_source_ids`: IDs of ancestor/space/page nodes whose direct restrictions caused the page to be classified non-clean. Empty list when `no_read_restrictions_seen`.

### Storage

Two stores, one ownership:

| File | Purpose | Tracked |
|---|---|---|
| Per-page frontmatter (3 fields) | Fast-read for MCP filter; human-debuggable | Yes — `output/raw/.../*.md` is committed if the rest of `raw/` is |
| `output/_access/access-manifest.jsonl` | Per-page detail incl. user/group IDs and full API raw | **Gitignored** (contains user emails, account IDs) |
| `output/_access/spaces.json` | Per-space audience cache, paginated full raw | **Gitignored** (contains group IDs) |
| `output/_access/access-summary.md` | Sanitized human rollup — counts + folder-source names only | Committed |

Frontmatter never carries PII — no usernames, emails, group names, or account IDs. Those live in the gitignored manifest where access can be tightened later if needed.

### Classifier (priority order — first match wins)

```python
def classify(direct, ancestors, space):
    if direct is None or direct.error or ancestors is None or any(a.error for a in ancestors):
        return "unknown"
    if space is not None and space.default_audience == "restricted_space":
        return "space_restricted"
    if direct.read.has_restrictions:
        return "restricted_direct"
    if any(a.read.has_restrictions for a in ancestors):
        return "restricted_inherited"
    return "no_read_restrictions_seen"
```

A 403 on the space endpoint is non-fatal — the `space` layer drops out of `restriction_check`, but classification still proceeds from `direct + ancestors`.

### Field ownership

The three access-owned fields are exclusively written by:

- Step 1 (now): `scripts/access_metadata_probe.py` — one-shot rewrite on existing markdown.
- Step 2 (next): `src/sukb/ingest/puller.py` — refreshed on every sync, via the same shared helpers (`restrictions.py`, `spaces.py`).

`restricted_to` (a stale Phase-1 puller-owned field) is **not** touched by the probe — Step 2 decides whether to drop it from the puller's frontmatter writer.

## Observed evidence (probe run, 2026-05-19)

This ADR is written *after* a real probe run, per the plan's "ADR after Step 1" rule. The full inputs/outputs are in `output/_access/`. Headline numbers from a 34-page ITSAI sweep:

| Metric | Value |
|---|---:|
| Pages classified | 34 / 34 |
| `no_read_restrictions_seen` | 31 |
| `restricted_inherited` | 3 |
| `restricted_direct` | 0 |
| `space_restricted` | 0 |
| `unknown` | 0 |
| Layer coverage | `direct + ancestors + space` for all 34 |
| Restriction sources surfaced | 1 — folder `1069121551` "Summer Intern 2026" |
| Manifest errors | 0 |

The three `restricted_inherited` pages are the Summer Intern test pages (Julian, Shahaan, Rob). Page-level direct restrictions on each were empty — the ancestor walk is what caught the restriction on the parent folder. This is the exact false-clean case ADR-0006 would have produced.

### Resolved questions

The plan listed four open questions resolved by Step 1 evidence; here's how each landed:

1. **Does SU's Confluence expose space permissions to the sync token?** Yes. `/spaces/{id}/permissions` returned 200 with 225 paginated permission records for ITSAI (9 pages of results). The `spaces.json` cache captures all of them. The Phase 1.1 heuristic ("non-empty results = `su_community`") is intentionally coarse — sufficient to confirm ITSAI is broadly accessible (which 225 records makes obvious), insufficient to distinguish a narrow allowlist within those records. Tightening the classifier requires reading the raw data and writing a "restricted_space" heuristic; deferred to a future ADR.
2. **Does the puller currently dedupe ancestor lookups across pages?** It deduplicates ancestor *title* lookups via `_ancestor_title_cache`. Ancestor *restriction* lookups are new in Phase 1.1 — the probe adds `AncestorRestrictionCache`, which the Step 2 puller integration will reuse via the shared `restrictions.py` module.
3. **Do restriction endpoints return user/group IDs to the sync token, or only counts?** **Full user objects.** The byOperation response includes `accountId`, `email`, `publicName`, `displayName`, `accountType`, and `accountStatus` per restricted user. Phase 1.1 normalizes only the `accountId` into the manifest's `user_ids` array; everything else stays in `raw` for re-parse if needed. Future per-user expansion does not require escalating to admin scope on SU's tenant.
4. **Should `errors` in manifest entries promote to alerts?** Not for v1 — current `errors` count on a 34-page corpus is 0. The summary surfaces unknown/error counts in plain text; if growth makes this noisy we'll add a separate `_access/errors.jsonl`. Decision deferred until corpus exceeds ~200 pages.

### Sanitization audit (access-summary.md)

`access-summary.md` is committed to the repo. The committed file is:

- Counts by `visibility_signal` and `restriction_check` shape — yes
- Folder/page IDs and titles that act as restriction *sources* — yes (folder `1069121551` "Summer Intern 2026")
- Account IDs, user emails, display names — **no**
- Titles of restricted *destination* pages (Julian/Shahaan/Rob Test) — **no**
- Raw API responses — **no**

Verified by grep against the generated `access-summary.md` post-write: no `accountId`, no `@syr.edu` strings, no restricted-page titles.

## Consequences

**Positive:**

- Honest classification — Summer Intern pages classify correctly the moment Step 2 (puller integration) ships, and ARE classified now via the probe's one-shot rewrite. ADR-0006's false-clean case is resolved.
- Two layers of defense: PAT-scope (unchanged) + MCP read-path filter (added in Step 3).
- Shared helpers (`restrictions.py`, `spaces.py`) mean the probe and puller can't drift apart on classification logic.
- API-shape uncertainty is resolved by probe evidence rather than guesswork — user IDs ARE returned, so the manifest carries normalized data for future per-user expansion without re-pulling.
- Reversible: Phase 1.1 is frontmatter-only over existing markdown. If we need to roll back, `git diff` shows exactly which fields changed.

**Negative / trade-offs accepted:**

- Per-page sync now makes ~2–3 extra API calls (direct restriction + amortized ancestor restriction + amortized space). At 5 req/sec ceiling and a 34-page corpus, this adds ~5–7 seconds. Re-measure at 4k pages.
- The space-permission classifier ("non-empty results = `su_community`") is conservative. A space with 5 narrow-allowlist permission records would still classify `su_community` today. Acceptable for ITSAI (225 records, clearly broad). Tightening requires a future ADR with classifier evidence from a known-restricted space.
- The manifest contains user emails / account IDs / display names. It's gitignored, but on-disk it's plaintext. Treat the manifest like `.env` — don't share it.
- `output/_access/access-summary.md` IS committed; sanitization rules above are the discipline that keeps it safe to share.

## Alternatives considered

- **Hold the ADR-0006 line: descriptive-only, no live restriction calls.** Rejected — Phase 1.1's whole point is to compute honest values. The cost of ~3 API calls per page is small and the false-clean case is real.
- **Per-user RBAC via OAuth service account in Phase 1.1.** Out of scope — the underlying OAuth flow / identity-broker isn't built. Phase 1.1 lays groundwork (manifest has normalized account IDs) without committing.
- **Split `raw/public/` vs `raw/internal/` folders.** Rejected (same reason ADR-0006 rejected it): premature without an audience-separation model. The MCP read-path filter is the v1 enforcement.
- **Heuristic-based space classifier with body-of-evidence rules (e.g., flag spaces with <10 permission records as `restricted_space`).** Tempting but unfounded — we'd be writing a classifier against one observed space. Defer until we have evidence from at least one known-restricted SU space.
- **Skip `space_restricted` entirely from the vocabulary.** Rejected — the slot is cheap, and the future case where SU adds a private space is plausible. Better to reserve the value now.

## References

- Predecessor planning doc: [docs/phase-1.1-plan-2026-05-19.md](../phase-1.1-plan-2026-05-19.md)
- API-shape probe doc: [docs/access-metadata-plan-2026-05-19.md](../access-metadata-plan-2026-05-19.md)
- Generated artifacts (probe outputs): [../../output/\_access/access-summary.md](../../output/_access/access-summary.md)
- Shared helpers: [src/sukb/ingest/restrictions.py](../../src/sukb/ingest/restrictions.py), [src/sukb/ingest/spaces.py](../../src/sukb/ingest/spaces.py)
- Probe script: [scripts/access\_metadata\_probe.py](../../scripts/access_metadata_probe.py)
- Atlassian byOperation endpoint: <https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-restrictions/>
- Atlassian space-permissions v2 endpoint: <https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space-permissions/>
- ADR-0006 (superseded): [0006-visibility-metadata-is-descriptive.md](0006-visibility-metadata-is-descriptive.md)
