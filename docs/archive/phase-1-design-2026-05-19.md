# Phase 1 Design Freeze — Metadata Schema Hardening (G1)

_Date: 2026-05-19. Status: **G2 APPROVED by codex (2026-05-19) + nit applied for skip-helper parallelism. 197/197 tests green. `git diff --check` clean. Working tree uncommitted on `main` — awaiting Julian's decision on next step (re-ingest / eval / commit prep).**_

## What this is

The Phase 1 design for the metadata-hardening work scoped in [aaron-meeting-2026-05-18-followups.md](aaron-meeting-2026-05-18-followups.md). Covers follow-ups **F-01, F-02, F-04, F-05, F-06 (partial), F-10**. F-03 (edit-cadence report) is owned by Robert. F-13 (classifier eval) is Shahaan's lane.

This is the design that codex should review against the codebase. After approval, I implement on a `phase-1-metadata-schema` branch and stop again at G2 for diff review.

## Principle driving the design

> **Julian's ingest lane stores observed facts. Shahaan's classifier lane assigns interpretive labels. Report scripts compute derived classifications dynamically from facts.**

This is what changed between G0 and G1: we are not baking `size_class` or `staleness_class` into page frontmatter. Aaron's thresholds (2y/5y for staleness, 8k tokens for oversize) will move; reports compute them on demand.

## Decisions locked (from G0, revised per codex's separation principle)

| Decision | Locked value |
|---|---|
| Phase 1 is additive only — no field removals, no oversize stubbing | ✅ |
| Keep existing `labels`, add `tags_original` alongside | ✅ |
| Visibility metadata is descriptive best-effort, not access enforcement | ✅ ADR-0006 |
| Don't bake derived classes (`size_class`, `staleness_class`) into frontmatter | ✅ revised at G1 |
| `tags_normalized`, `audience`, `doc_type`, etc. — classifier lane (Shahaan) owns | ✅ ingest must preserve, never overwrite |
| `include-labels=true` is opportunistic with fallback to current separate calls | ✅ |
| Phase 3 scripts (`tag_inventory.py`, `lint_wiki_citations.py`) ship in same PR if tests stay clean | ✅ |
| Short ADR-0006 for the visibility model | ✅ |

## Frontmatter schema v2 — additions

Eight new fields. All factual / directly observed, none derived.

| Field | Type | Default | Source |
|---|---|---|---|
| `word_count` | int | computed | count words in converted markdown body |
| `char_count` | int | computed | `len(body)` |
| `token_estimate` | int | computed | `char_count / 3.5` (heuristic) or tiktoken if dep available |
| `attachment_count` | int | computed | count of files in `output/attachments/<page-id>/` |
| `tags_original` | list[str] | from labels endpoint | copy of Confluence labels at ingest time |
| `visibility_signal` | enum | `accessible_to_sync_user` | observed: page fetched OK = accessible; restriction endpoint non-empty = `restricted_direct`; not yet checked = `unknown` |
| `restriction_check` | enum | `not_checked` | `not_checked` (V1 default), `checked_direct` (we called `/restriction/byOperation` for this page), `failed` (call errored) |
| `restricted_to` | list | `[]` | raw response of restriction endpoint when called; otherwise empty |

V1 behavior for visibility: **we don't actively call the restriction endpoint** in this phase. All successfully-fetched pages get `visibility_signal: accessible_to_sync_user` and `restriction_check: not_checked`. The schema slots exist so when we add the active check later, no re-ingest is needed.

## What we are NOT adding (rationale)

| Excluded field | Why excluded |
|---|---|
| `size_class` | Derived classification. Thresholds move. Reports compute dynamically from `word_count` / `token_estimate`. |
| `staleness_class` | Same — Aaron's 2y/5y thresholds belong in report scripts, not in 29+ page files. Reports compute from `last_modified` / `days_since_modified`. |
| `tags_normalized` | Classifier output. Shahaan's lane writes it. Ingest must not write or clobber. |
| Folder split `raw/public/` vs `raw/internal/` | Premature per codex. Visibility fields are sufficient until we have a real service-account model. |
| Quarantine stubs for restricted pages | Premature — we don't actively detect restricted pages in V1. |
| `restricted_inherited_possible` | Reads like evidence when we haven't checked. Caveat lives in ADR + docs. |

## Classifier-field preservation (confirmed real bug — Phase 1 fix)

**Codex confirmed at G1 review**: `build_frontmatter()` always writes `audience: null / doc_type: null / tools: [] / topics: []` and `puller.py` writes a fresh frontmatter block without reading the existing one. Classifier preservation is real Phase 1 work.

**Fix**: before writing, the puller reads `target_path` (if it exists), extracts the preserved keys from the existing frontmatter, and merges them into the new frontmatter dict. New ingests (target file doesn't exist) get the default-empty values.

**Codex correction on field classification**: `maintenance_signal` is currently pipeline-derived from `days_since_modified`, not Shahaan's classifier output. Treat it as legacy pipeline-derived metadata, not classifier-owned. Puller continues to write it for backward compatibility; new reports should compute staleness dynamically from `last_modified` / `days_since_modified`.

**Classifier-owned keys** (puller must read existing value from target_path and preserve if non-empty/non-default):
- `audience`, `doc_type`, `tools`, `topics`
- `tags_normalized` (future — not yet written by anything)
- Anything under a future `classifier:` block

**Puller-owned keys** (always overwritten on sync):
- All identity fields (`page_id`, `title`, `source_url`, etc.)
- `version`, `last_modified`, `contributors`, `content_hash`, `synced_at`, `last_sync_status`
- `labels`, `tags_original`
- All new size fields (`word_count`, `char_count`, `token_estimate`, `attachment_count`)
- `days_since_modified`
- `maintenance_signal` ← legacy pipeline-derived, kept for backward compat
- `visibility_signal`, `restriction_check`, `restricted_to`
- `conversion_warnings`

## Sync loop changes (metadata-first with fallback)

**Current flow** (verified via `src/sukb/ingest/puller.py`):
```
list_pages(space, body-format=storage)   # bodies fetched upfront
for page in pages:
    if state.unchanged(version, content_hash): skip
    body_md = convert(page.body)
    labels = get_page_labels(page.id)     # separate call
    write_page(...)
```

**Proposed flow:**
```
metas = list_pages_metadata(space)        # no body
for meta in metas:
    if state.unchanged(meta.id, meta.version):
        skip                              # no body fetch, no convert, no classify
    try:
        full = get_page_full(meta.id,
                             body_format='storage',
                             include_labels=True)   # opportunistic
        labels = full.labels
    except UnsupportedParameter:
        full = get_page(meta.id, body_format='storage')
        labels = get_page_labels(meta.id)            # fallback
    body_md = convert(full.body)
    write_page(..., labels=labels, tags_original=labels)
```

**Key constraint**: `include_labels` is documented for v2 GET-by-id. The list endpoint we use may or may not support it. Implementation must test the param against the actual endpoint and fall back cleanly — codex flagged this and I'm not assuming either way.

**Steady-state win**: when nothing changes, the puller pays one list call per space. No body fetches. No convert. No label calls. No file writes.

## Touch list

| File | Change |
|---|---|
| [src/sukb/ingest/frontmatter.py](../src/sukb/ingest/frontmatter.py) | Add 8 new fields + computation helpers (`compute_word_count`, `compute_token_estimate`, `count_attachments`); add read-modify-write logic that preserves classifier-owned keys |
| [src/sukb/ingest/puller.py](../src/sukb/ingest/puller.py) | Switch to metadata-first listing; opportunistic `include-labels` with fallback; pass labels into frontmatter writer as both `labels` and `tags_original` |
| [src/sukb/ingest/state.py](../src/sukb/ingest/state.py) | Likely no change — verify version-only diff before body fetch works with existing state shape |
| `docs/decisions/0006-visibility-metadata-is-descriptive.md` | New ADR |
| `scripts/tag_inventory.py` | New — Phase 3 |
| `scripts/lint_wiki_citations.py` | New — Phase 3 |
| `tests/` | New tests (see below) |
| `output/raw/**/*.md` | Re-ingested to populate new fields (no separate migration script; puller is idempotent) |

## Phase 3 scripts (shipping alongside Phase 1)

### `scripts/tag_inventory.py`
- Walks `output/raw/`, collects all `labels` (== `tags_original` in V1).
- Emits frequency table + proposed seed taxonomy → `research/kb-ingestion-project/tag-inventory-2026-05-19.md`.
- Read-only; no corpus mutation.

### `scripts/lint_wiki_citations.py`
- Walks `output/wiki/*.md`.
- Extracts every `[[<digits>]]` and every `synthesizes:` page-id.
- Asserts each resolves to a real `output/raw/.../<digits> - *.md`.
- Exits non-zero on failure. Wired into the test suite so CI catches drift.

## ADR-0006 outline

```
# 0006 — Visibility metadata is descriptive, not enforcement

Status: accepted
Date: 2026-05-19

## Context
Aaron asked about page-restriction handling. Investigation:
- Atlassian REST does not reliably return inherited restrictions.
- Our V1 auth surface is a PAT — "what the sync user can read" IS the access
  boundary, regardless of what frontmatter says.
- Aaron explicitly approved "public-only ingest" for V1.

## Decision
Frontmatter carries visibility_signal / restriction_check / restricted_to as
best-effort descriptive metadata. Downstream consumers (MCP, eval, agents)
MUST NOT treat these fields as authoritative for access control. Access is
enforced by what the sync user's token can fetch, full stop.

## Consequences
+ Phase 1 ships without solving RBAC.
+ Schema slot exists for when OAuth/service account arrives.
+ No raw/public vs raw/internal folder split in V1.
+ No quarantine/ folder in V1.
- Anyone reading frontmatter could mistake the field for a permission boundary
  → mitigated by docstring in frontmatter.py + this ADR.

## Alternatives considered
- Per-page restriction check via /restriction/byOperation: deferred. Costs an
  extra API call per page; inherited restrictions still not covered.
- GraphQL for full restriction graph: out of scope for prototype.
- Folder split now: premature without a real audience-separation model.

## Supersedes
None.
```

## Test plan

| Test | Asserts |
|---|---|
| Frontmatter round-trip | Existing fixture + 8 new fields → write → read → all values match |
| word_count / char_count / token_estimate | Known body of 1,000 words / 5,000 chars → values match within tolerance |
| attachment_count | Page with 3 attached files → count is 3; page with none → 0 |
| tags_original mirrors labels | At ingest, both fields equal the labels-endpoint response |
| Classifier-key preservation | Pre-populate frontmatter with `audience: student`, `doc_type: how_to`, re-run ingest → values still `student` and `how_to`, not null |
| Sync skip when version unchanged | Mock state with `version=5`, fetch returns `version=5` → no body fetch, no write |
| Sync triggers when version bumps | Mock state with `version=5`, fetch returns `version=6` → body fetched, file rewritten |
| `include_labels` fallback path | Mock endpoint that errors on `include-labels` param → falls back to separate `/labels` call |
| Citation lint | Wiki hub citing a real page-id → pass; citing a non-existent page-id → fail |

## Eval gate (must pass before G2 merge)

- Run existing 15-query baseline (per [eval-baseline-2026-05-13.md](eval-baseline-2026-05-13.md)).
- **Acceptance**: 14/15 (✅ ⚠️ ✅... ✅) unchanged. Cost ≤ $0.10 above baseline.
- **Block-on-fail**: any quality regression → frontmatter additions broke retrieval → fix before merge.

## Re-ingest as part of this PR

The puller is idempotent. After the schema change lands locally:
- Run `python -m sukb.ingest.puller` against the existing space.
- Expect all 29 pages to rewrite with new fields populated; no body changes.
- Diff should show *only* frontmatter additions, no content changes.
- Commit the re-ingested files in the same PR as the schema change. One unit of work, one review.

## G1 review answers (codex, 2026-05-19)

1. **`include_labels` on list endpoint** — don't rely on list support. Metadata list without labels, then changed-page GET-by-id with `include-labels=true` opportunistically, fallback to `/pages/{id}/labels`. ✅ as designed.
2. **`token_estimate` heuristic** — `ceil(char_count / 3.5)`. No `tiktoken` dep. This is report/routing metadata, not billing-grade.
3. **`attachment_count`** — filesystem. Means "attachments successfully mirrored locally," not "upstream says attachments exist." Aligns with our attachment-verification principle.
4. **Classifier-key preservation** — confirmed not preserved. Fix in Phase 1 by reading existing frontmatter from `target_path` before writing and merging preserved keys. (See "Classifier-field preservation" section above.)
5. **YAML field ordering** — group new observed fields *near related existing fields*, not all at bottom. Long-term readability > diff clarity:
   - `labels`, `tags_original` together
   - `word_count`, `char_count`, `token_estimate`, `attachment_count` near maintenance/sync diagnostics
   - `visibility_signal`, `restriction_check`, `restricted_to` near source/provenance
6. **`restricted_to` shape** — keep `list` default. Document "currently empty; future shape follows API response." Don't invent user/group object shape until we actually call the restriction endpoint.
7. **ADR naming** — `0006-visibility-metadata-is-descriptive.md` fits the existing pattern. ✅

## What comes after G1 approval

If codex signs off:
1. Implement frontmatter additions + classifier-key preservation.
2. Implement metadata-first sync with fallback.
3. Write Phase 3 scripts.
4. Re-ingest existing pages.
5. Tests green.
6. Run eval baseline — confirm 14/15 still holds.
7. Write ADR-0006.
8. Open PR on `phase-1-metadata-schema` branch.
9. Stop at G2. Codex reviews diff; Julian decides push.

Phase 2 (hierarchical index) is downstream and gated on a fresh pre-snapshot eval to justify it.
