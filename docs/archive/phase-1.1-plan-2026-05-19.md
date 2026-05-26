# Phase 1.1 Plan — Access Classification

_Date: 2026-05-19. Status: planning only. No implementation in this file._

Builds on [`access-metadata-plan-2026-05-19.md`](./access-metadata-plan-2026-05-19.md). Resolves the open schema/process decisions left there, lays out the implementation order, and explicitly defers API-owned lifecycle metadata to a later phase so this one stays scoped.

## Goal

Turn the stubbed `visibility_signal: accessible_to_sync_user` / `restriction_check: not_checked` fields into honest, computed values across the corpus, backed by a separate access manifest. Keep the queryable corpus correct for v1, and lay groundwork for per-user expansion without committing to RBAC.

Phase 1.1 is **access-classification only**. Pipeline-wide metadata improvements (authorship facts, attachment metadata, etc.) come in Phase 1.2 — see the "Deferred to Phase 1.2" section at the bottom.

## Scope

**In:**

- Direct + ancestor + space-level restriction classification for every page in `output/raw/`
- New manifest at `output/_access/access-manifest.jsonl` keyed by `page_id`
- Space-level cache at `output/_access/spaces.json`
- Human-readable rollup at `output/_access/access-summary.md` (counts and folder-level sources only — no restricted-page titles, no account/group IDs)
- Frontmatter updates (in-place) to existing pages — **only the three access-owned fields** (`visibility_signal`, `restriction_check`, `restriction_source_ids`)
- MCP/indexer enforcement: only `visibility_signal: no_read_restrictions_seen` is queryable
- Per-ancestor and per-space in-memory caches to keep the API call budget bounded
- Shared helper modules (`restrictions.py`, `spaces.py`) callable by both the probe script and the puller

**Out (explicitly deferred):**

- Per-user / per-group RBAC enforcement
- Live permission checks at query time
- Sandbox / student-account testing
- Removing the existing `(Test)` and `Summer Intern 2026` path-segment exclusion (kept as belt-and-braces for now; superseded later)
- Historical version body capture
- Generating `output/_views/public/`
- Re-pulling existing pages — Phase 1.1 runs over current `output/raw/` in place
- **API-owned lifecycle fields in frontmatter** (`author_id`, `owner_id`, `created_at`, `parent_id`, `parent_type`, `position`, `version_*`) — deferred to Phase 1.2
- **Tighter attachment metadata** (`upstream_attachment_count`, `upstream_attachment_bytes`, `attachment_media_types`) — deferred to Phase 1.2

## Field ownership

To avoid the puller silently overwriting access classifications (and vice versa), each frontmatter field has exactly one owner.

| Owner | Fields | Who writes them |
|---|---|---|
| **Access-owned** (Phase 1.1) | `visibility_signal`, `restriction_check`, `restriction_source_ids` | Step 1: the probe script. Step 2+: the puller (the probe stops touching frontmatter once the puller is integrated). |
| Puller-owned (existing) | `page_id`, `title`, `space_key`, `ancestor_path`, `version`, `last_modified`, `labels`, `word_count`, `char_count`, `token_estimate`, `attachment_count`, `tags_original`, plus the existing compatibility fields (`audience`, `doc_type`, etc.) | The puller, overwritten each sync. |
| Classifier-owned (existing, separate concern) | `doc_type`, `tools`, `topics`, `audience` if the chat-side classifier writes them | The existing classifier, preserved across re-sync. **Not the same thing as access-owned.** Naming this out explicitly to avoid the prior conflation. |

**Rule:** when the puller integrates the access logic (Step 2), the access-owned fields become puller-owned in the same sense — refreshed on every sync. The probe script stops being a frontmatter writer at that point.

## Decisions locked (deltas from the existing plan)

ADR-formalized **after** Step 1, once the probe has confirmed API shapes — not before. Listed here as plan-decisions to guide the probe; ADR text captures the observed evidence.

| Decision | Choice | Replaces |
|---|---|---|
| Space-level access | Attempt one call per space; cache in `spaces.json`. If the endpoint 403s, mark `restriction_check` array as `[direct, ancestors]` (no `space` entry) and continue. Don't block the corpus on it. | Open Q2 in the prior plan |
| Add `space_restricted` to `visibility_signal` vocabulary | Yes — applied **only when space check succeeded and returned a restricted-space audience.** Skipped space → page classified by direct + ancestors only. | Vocabulary list in `access-metadata-plan-2026-05-19.md` lines 311–316 |
| `restriction_check` shape | Array of checked layers, e.g. `["direct", "ancestors", "space"]` or `["direct", "ancestors"]`. Empty array means nothing was checked. | Enum string |
| Raw API response storage in manifest | Always store `raw` per restriction entry (even `{}` when no restrictions) — consistency for re-parse | Conditional storage (existing plan line 403) |
| `_access/` git tracking | `access-summary.md` committed (sanitized — see below); `.jsonl` + `spaces.json` gitignored | Open Q4 |
| Public-only views | Skip for v1 — MCP enforces at read path | Open Q5 |
| Coexistence with path-segment exclusion | Logical OR for now; remove heuristic in a follow-up ADR after classifier verified over a full sync | New |
| ADR timing | After Step 1 probe — backed by observed data, not assumptions | New (Codex review correction) |

## Artifacts

```
SU_AI_Intern/prototypes/su-kb-pipeline/
├── scripts/
│   └── access_metadata_probe.py          # new — standalone classifier (Step 1)
├── src/sukb/ingest/
│   ├── puller.py                         # modified in Step 2 — folds probe logic in
│   ├── restrictions.py                   # new — restriction-fetching helpers (shared with probe)
│   └── spaces.py                         # new — space-permission helper (shared with probe)
├── output/
│   ├── _access/
│   │   ├── access-manifest.jsonl         # gitignored — generated each sync
│   │   ├── spaces.json                   # gitignored — per-space audience cache
│   │   └── access-summary.md             # committed, sanitized — see rules below
│   └── raw/.../<page-id> - <title>.md    # frontmatter updated in place (three access-owned fields only)
├── docs/
│   ├── decisions/000N-access-classification-v1.md   # new ADR — written after Step 1
│   └── STATUS.md                                     # updated by /log
└── tests/
    ├── fixtures/access/                  # canned API responses
    └── ingest/test_access_classification.py    # new
```

### Sanitization rules for `access-summary.md`

This file is committed to the repo, so it can be read by anyone with repo access (potentially broader than the queryable corpus's audience). Allowed contents:

- Counts by `visibility_signal` value
- Counts by `restriction_check` shape (e.g., "32 pages: full check; 2 pages: space skipped")
- Folder/page IDs that act as **restriction sources** (e.g., `1069121551`) and their titles — these are nodes that exist in the visible tree and are already known by ID to anyone reading the puller's other outputs
- Count and category of `unknown` / errored pages
- Per-space audience summary
- Timestamp of the run

Disallowed:

- Titles of restricted pages (would leak topic/structure even when bodies are protected)
- Account IDs, user IDs, group IDs from the manifest
- Raw API responses
- User-readable names or emails

In short: aggregate counts + the names of restriction *sources* (folders), never the names of restricted *destinations* (pages).

## Schemas

### Frontmatter (modify-in-place; preserve everything else)

```yaml
# Access-owned (Phase 1.1)
visibility_signal: no_read_restrictions_seen | restricted_direct | restricted_inherited | space_restricted | unknown
restriction_check: [direct, ancestors, space]   # array of layers actually checked
restriction_source_ids: ['1069121551']           # empty list if no restrictions
```

That is the entire Phase 1.1 frontmatter delta. No other fields are added or changed in this phase.

No user-facing PII (names, emails, account IDs, group IDs) — frontmatter never contains them. The manifest carries those; frontmatter only carries the classification signal.

### Manifest entry (`access-manifest.jsonl`, one JSON per line)

```json
{
  "page_id": "1068171339",
  "title": "Julian Test 1st Page",
  "space_key": "ITSAI",
  "visibility_signal": "restricted_inherited",
  "restriction_check": ["direct", "ancestors", "space"],
  "checked_at": "2026-05-19T12:00:00Z",
  "checked_with_account_id": "<julian's accountId>",
  "direct_restrictions": {
    "read":   {"has_restrictions": false, "user_ids": [], "group_ids": [], "raw": {}},
    "update": {"has_restrictions": false, "user_ids": [], "group_ids": [], "raw": {}}
  },
  "ancestor_restrictions": [
    {
      "source_id": "1069121551",
      "source_type": "folder",
      "source_title": "Summer Intern 2026",
      "read":   {"has_restrictions": true, "user_ids": ["accountid:abc..."], "group_ids": [], "raw": {}},
      "update": {"has_restrictions": true, "user_ids": ["accountid:abc..."], "group_ids": [], "raw": {}}
    }
  ],
  "space": {
    "key": "ITSAI",
    "default_audience": "su_community",
    "checked_at": "2026-05-19T12:00:00Z",
    "raw": {}
  },
  "errors": []
}
```

`raw` is required, even if empty `{}` for cases where no restrictions exist. The point is consistency — every entry has the same shape, every restriction has its raw payload available for re-parse.

If space check was skipped (e.g., token lacked scope), `space` is `null` and `restriction_check` omits `"space"`. `errors` captures the reason.

### Space cache (`spaces.json`)

```json
{
  "ITSAI": {
    "key": "ITSAI",
    "name": "Artificial Intelligence (AI)",
    "homepage_id": "483525103",
    "checked_at": "2026-05-19T12:00:00Z",
    "default_audience": "su_community",
    "raw": {}
  }
}
```

`default_audience` values: `su_community` | `restricted_space` | `anonymous` (unlikely for SU) | `unknown` (check errored) | `skipped` (check deliberately not attempted).

## Visibility logic (priority order — first match wins)

```python
def classify(direct, ancestors, space):
    # space may be None if check was skipped (e.g., token lacked scope)
    # direct and ancestors are required for any classification at all

    if direct is None or ancestors is None:
        return "unknown"
    if any_unexpected_error_in(direct, ancestors, space):
        return "unknown"

    # space_restricted only applies when we successfully checked and got a restricted result
    if space is not None and space.default_audience == "restricted_space":
        return "space_restricted"

    if direct.read.has_restrictions:
        return "restricted_direct"
    if any(a.read.has_restrictions for a in ancestors):
        return "restricted_inherited"

    # Direct + ancestors clean. Space may be skipped, but that's not an error — proceed.
    return "no_read_restrictions_seen"
```

Conservative on uncertainty: any unexpected response, 403 from direct/ancestor endpoints, or shape mismatch → `unknown`, treated as restricted by the MCP. Space skipped is not an error — it's a known limitation, and the page is still classified by direct + ancestors.

## Phasing

### Step 1 — Standalone read-only probe (`scripts/access_metadata_probe.py`)

**First run is read-only.** No frontmatter writes. No ADR yet. Purpose: confirm API response shapes against the live SU Confluence so the ADR and downstream code are backed by observed data.

**Inputs:**

```
--space ITSAI                 # required; can repeat for multi-space
--page-id <id>                # optional; if absent, walks all pages in --space
--out output/_access/access-manifest.jsonl
--spaces-cache output/_access/spaces.json
--summary output/_access/access-summary.md
--dry-run                     # classify + print, write nothing (default for the first run)
--update-frontmatter / --no-update-frontmatter   # default OFF until shapes are confirmed
```

**Behavior:**

1. Load creds from `.env`. Determine `checked_with_account_id` once (`GET /wiki/rest/api/user/current`).
2. For each space referenced:
   - Attempt `GET /wiki/rest/api/space/{key}/permission` (or v2 equivalent).
   - On success: classify `default_audience`, cache in memory.
   - On 403 / unexpected: cache `default_audience: skipped`, capture the error reason in `spaces.json`.
3. For each page (read `page_id` from frontmatter or from `GET /spaces/{id}/pages`):
   - Fetch direct restrictions (`/restriction/byOperation`)
   - Fetch ancestor chain; for each novel ancestor (not in memory cache), fetch its restrictions
   - Resolve ancestor titles via the per-page or per-folder endpoint the puller already calls
   - Compute `visibility_signal` per the logic above
   - Build manifest record
4. Write all outputs via atomic temp-then-rename pattern: temp → `access-manifest.jsonl`, `spaces.json`, `access-summary.md`.
5. **Frontmatter update is gated by `--update-frontmatter`.** Default off. First run produces manifest + summary only; the human reads them, decides shapes look right, then opts in to the rewrite.

**Rate limit:** 5 req/sec (matches puller). Ancestor-restriction lookups are cached per `ancestor_id` so a 34-page corpus with a shared `AI Workspace` parent makes one ancestor call, not 34.

**Acceptance checks (Step 1 success):**

- The probe completes without crashing.
- Summer Intern 2026 folder children classify as `restricted_inherited`.
- `restriction_source_ids` contains `1069121551`.
- The ancestor walk actually fetched a non-empty restriction (assertion in the probe; logged in summary).
- AI / Claude folder pages classify as `no_read_restrictions_seen`.
- Manifest entries have populated `direct_restrictions.raw` and `ancestor_restrictions[].raw` (so re-parse is possible later).
- `access-summary.md` is sanitized per rules above.

**Space-level is explicitly NOT a Step 1 success requirement.** Three space outcomes are all acceptable:

- Space check succeeds, ITSAI is `su_community` → expected, great.
- Space check succeeds, ITSAI is `restricted_space` → surprising, would change classifications.
- Space check 403s → space marked `skipped`, classification still works from direct + ancestors.

**Failure modes handled (probe-level):**

- Token lacks scope on direct-restriction endpoint → `restriction_check: []`, `visibility_signal: unknown`, error captured in manifest entry's `errors` array. Probe continues. Summary surfaces these.
- Restriction endpoint returns counts but not IDs → store counts + `raw`, mark `has_restrictions` boolean. Classification still works for v1; per-user expansion later requires escalating to elevated scope.
- Page deleted upstream → mark `unknown` and log; don't crash.

**Idempotent + crash-safe:** atomic rename pattern means a crashed run leaves the previous outputs intact. Re-running produces the same output for unchanged permissions.

### Step 1.5 — ADR

After Step 1 has run successfully (read-only) and you've eyeballed the manifest + summary, write the ADR:

```
/decide access-classification-v1
```

The ADR captures, with concrete probe evidence:

- The locked decisions from the table above
- Observed response shapes (whether IDs come through vs counts)
- Whether space-permission endpoint was accessible
- Any deviations from the plan that the probe surfaced

Then re-run Step 1 with `--update-frontmatter` to write the access-owned fields to the existing 34 markdown files.

### Step 2 — Pipeline integration (`src/sukb/ingest/puller.py`)

Once Step 1 is complete and the ADR is written, fold the same logic into the puller. New per-page sequence:

```
1. Fetch page metadata (current behavior)
2. Fetch labels (current behavior)
3. Fetch ancestors + resolve titles (current behavior, but now shared cache with restrictions)
4. Fetch direct restrictions  (NEW)
5. For each novel ancestor: fetch ancestor restrictions  (NEW, cached)
6. Ensure space is in spaces cache; fetch if not  (NEW)
7. Compute visibility_signal
8. Convert body → markdown (current behavior)
9. Write/update markdown with frontmatter — including the three access-owned fields
10. Write manifest record (append to in-progress JSONL; atomic-rename at end)
```

Shared helpers `src/sukb/ingest/restrictions.py` and `spaces.py` mean the probe script imports the same code the puller uses — no logic duplication. **At this point, the puller becomes the owner of the access-owned fields** (it refreshes them on every sync). The probe script is retained for one-off audits but stops being the canonical frontmatter writer.

**Cache lifetime:** in-memory for the duration of one puller invocation. The puller re-fetches restrictions on each run because permissions may have drifted. If/when the corpus grows past ~5k pages and runtime becomes a concern, cache to disk with TTL — out of scope for Phase 1.1.

**Field-ownership audit during Step 2:** verify the puller does not preserve `visibility_signal` / `restriction_check` / `restriction_source_ids` from old frontmatter; it must overwrite them. The "preserve classifier-owned fields across re-sync" logic (existing puller behavior per `access-metadata-plan-2026-05-19.md` line 30) refers to a *different* set of fields (`doc_type`, `topics`, etc. — see the field-ownership table above). Add an explicit `ACCESS_OWNED_FIELDS` constant in `src/sukb/ingest/__init__.py` (or wherever the existing ownership convention lives) so the distinction is enforced in code, not just documentation.

### Step 3 — MCP / indexer enforcement

Update `src/sukb/chat/` retrieval surfaces:

| Surface | Filter |
|---|---|
| `search` | `WHERE visibility_signal = 'no_read_restrictions_seen'` (or equivalent index-time exclude) |
| `get_page` | reject any `page_id` whose frontmatter / manifest has any other value, returning a clean "not available" response rather than the body |
| `list_index` | filter listings to allowed pages only (preserve folder hierarchy nodes whose subtree contains anything visible) |
| `list_hubs` | same |
| citation resolution | reject citations pointing at non-public pages; log to a structured warning channel |

Source of truth for the filter: frontmatter `visibility_signal` (fast — already loaded with the page). Manifest is consulted only if the indexer needs the allowlist detail, which v1 doesn't.

**Belt-and-braces:** keep the path-segment exclusion (`(Test)`, `Summer Intern 2026`) active. If either mechanism excludes a page, it's excluded. Once the classifier has been verified on a full sync for two weeks, write a follow-up ADR removing the path-segment heuristic for `Summer Intern 2026` (keep `(Test)` since that's about content quality, not access).

### Step 4 — Tests (`tests/ingest/test_access_classification.py`)

Synthetic API fixtures under `tests/fixtures/access/`. No live Confluence calls.

| Case | Expected |
|---|---|
| page with no restrictions, ancestors clean, space clean | `no_read_restrictions_seen`, `restriction_check: [direct, ancestors, space]` |
| page with no restrictions, ancestors clean, **space check skipped** | `no_read_restrictions_seen`, `restriction_check: [direct, ancestors]` |
| page with direct read restriction | `restricted_direct` |
| page in folder with read restriction | `restricted_inherited`, `restriction_source_ids` populated |
| page in `restricted_space` regardless of page/ancestor state | `space_restricted` |
| direct-restriction endpoint returns 403 | `unknown`; error captured in manifest |
| restriction endpoint returns counts only | `has_restrictions` boolean correct; classification still works |
| ancestor walk encounters a folder (not page) restriction | `restricted_inherited` with `source_type: folder` |
| MCP `search` excludes restricted/unknown pages | only `no_read_restrictions_seen` returned |
| MCP `get_page` rejects restricted pages | clean "not available" response |
| `list_index` filters listings correctly | restricted entries omitted; tree structure preserved |
| manifest is keyed by `page_id` | one record per `page_id`, last-write-wins |
| Summer Intern 2026 fixture | `restricted_inherited`, source `1069121551` |
| `access-summary.md` content audit | contains no restricted-page titles, no IDs |

## Open questions (genuinely undecided, resolved by Step 1 evidence)

1. **Does SU's Confluence expose space permissions to the sync token?** Probe will tell us. Plan handles both outcomes; no blocker.
2. **Does the puller currently dedupe ancestor lookups across pages?** If yes, easy hook for the restriction cache. If no, add it as part of Step 2. Need to read `puller.py` to confirm — first thing in Step 2.
3. **Do restriction endpoints return user/group IDs to the sync token, or only counts?** Determines whether the manifest can be populated with normalized IDs for future per-user expansion, or whether per-user expansion requires escalating to admin scope. Either way, Phase 1.1 ships.
4. **Should `errors` in manifest entries promote to actionable alerts somewhere?** v1 just lists them in `access-summary.md`. If the corpus grows to thousands of pages, a 1% error rate becomes 40+ entries; we may want a separate `_access/errors.jsonl`. Defer.

## Migration / rollout for the existing 34 ITSAI pages

The probe runs over the current `output/raw/` without a re-pull:

1. Run probe with `--dry-run` against ITSAI. Inspect `access-summary.md` and `access-manifest.jsonl`.
2. Write the ADR with observed shapes.
3. Run probe with `--update-frontmatter` against ITSAI. Verify the three access-owned fields on each page changed; verify everything else didn't (`git diff` should show only those three fields per page).
4. If `output/raw/` is git-tracked, commit the frontmatter update under one commit, ADR under another.
5. Run the MCP layer locally; verify Summer Intern pages no longer appear in `search` results, and AI/Claude pages do.
6. Once verified, Step 2 puller integration happens. Subsequent re-syncs maintain classification automatically.

If `output/raw/` is gitignored (likely — it's regenerated mirror content), still verify with `git status` that no unexpected files changed.

## Success criteria

After Step 1 `--dry-run` completes:

- `access-summary.md` exists and is sanitized per rules above.
- Counts add up: e.g., `34 pages classified, N no_read_restrictions_seen, M restricted_inherited (all via Summer Intern 2026 folder 1069121551), K unknown`.
- `access-manifest.jsonl` has 34 entries, each with `raw` payload populated.
- `spaces.json` has at least the ITSAI entry — `default_audience` is either `su_community`, `restricted_space`, or `skipped` (any of the three is acceptable).

After Step 1 `--update-frontmatter` completes:

- `grep -l "visibility_signal: no_read_restrictions_seen" output/raw -r | wc -l` matches the summary's count.
- Diff of each updated `.md` file shows only the three access-owned fields changed.

After Step 2 completes:

- A fresh puller run regenerates the manifest from scratch with identical classifications.
- The puller is the sole writer of access-owned fields; the probe is now a one-off audit tool.
- `ACCESS_OWNED_FIELDS` exists as an explicit constant in code; the puller's frontmatter-write logic uses it.
- Per-page wall time ≤ 2.5× pre-Phase-1.1 baseline.

After Step 3 completes:

- MCP `search` returns only `no_read_restrictions_seen` pages.
- `get_page("1068171339")` (a Summer Intern child — matches the manifest example above) returns a clean "not available" response.
- `list_index` shows the AI/Claude folder tree but not Summer Intern descendants.

After Step 4 completes:

- Test suite green; restricted/unknown/skipped-space cases all exercise the MCP filter at least once.
- One end-to-end test confirms the Summer Intern fixture round-trips correctly through ingest → classify → MCP filter → not-served.

## Deferred to Phase 1.2

These came out of the probe-findings inventory but are **not in Phase 1.1**. Capturing here so the inventory isn't lost.

### 1. Surface API-owned authorship and lifecycle facts

Add to frontmatter (Phase 1.2):

| Field | From API |
|---|---|
| `author_id`, `owner_id`, `last_owner_id` | `/pages/{id}` |
| `created_at` | `/pages/{id}` |
| `parent_id`, `parent_type`, `position` | `/pages/{id}` |
| `version_number`, `version_message`, `version_minor_edit`, `version_author_id` | `/pages/{id}.version` |

Keep `days_since_modified` (locally computed) as a derived field for backward compat.

Why later: this is a different concern from access classification. Bundling them into one phase risks a giant metadata refactor and blurs review focus. Ship access first, then lifecycle.

### 2. Tighten attachment metadata

Add to frontmatter (Phase 1.2):

```yaml
upstream_attachment_count: 5
upstream_attachment_bytes: 1248576
attachment_media_types: ['image/png', 'application/pdf']
```

Keep `attachment_count` as "mirrored locally" — same semantics.

### 3. Rate-limit budget re-check after Phase 1.2

Phase 1.1 adds ~2–3 calls per page (direct restrictions + amortized ancestor restrictions + amortized space). Phase 1.2 adds a few more (version detail, attachment listing). Re-measure at the end of 1.2 and decide whether the puller needs parallelism for full-corpus syncs (~4000 pages).

## Next action

Step 1, read-only:

1. Read `src/sukb/ingest/puller.py` to understand the auth/client pattern and the existing frontmatter-write helper.
2. Write `scripts/access_metadata_probe.py` reusing that auth/client. First substantive call: hit `/restriction/byOperation` on the Summer Intern folder (`1069121551`) and dump the raw JSON. That decides whether the manifest can carry normalized user/group IDs or has to fall back to counts-plus-raw.
3. Then space-permission check against ITSAI. That decides whether the `space` field in the manifest is populated or marked `skipped`.
4. Then walk all 34 ITSAI pages with the full classification logic, dry-run only.
5. Inspect `access-summary.md` and `access-manifest.jsonl`. Confirm shapes match expectations.
6. Write the ADR with observed evidence.
7. Re-run with `--update-frontmatter`.

ADR comes after the probe, not before — so it's grounded in what the API actually returns, not assumptions.
