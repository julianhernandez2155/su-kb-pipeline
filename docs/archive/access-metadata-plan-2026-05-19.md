# Access Metadata Plan - Phase 1.1

_Date: 2026-05-19. Status: planning only. No implementation in this file._

## Purpose

Phase 1 added schema-v2 frontmatter and reserved descriptive visibility fields, but the puller still writes:

```yaml
visibility_signal: accessible_to_sync_user
restriction_check: not_checked
restricted_to: []
```

That is honest for Phase 1, but not enough for a general queryable MCP. Phase 1.1 should keep pulling the full Confluence corpus while classifying which pages are safe for the v1 public/general MCP index.

The immediate goal is:

1. Keep all converted markdown files available in `output/raw/`.
2. Capture enough access metadata to distinguish unrestricted pages from directly or inherited-restricted pages.
3. Make v1 MCP search/read tools query only pages with no read restrictions seen.
4. Preserve enough raw access detail for future admin/user-aware filtering without committing to a full RBAC design yet.

## Current Phase 1 Behavior

Already implemented:

- Pull all visible ITSAI pages through Julian's sync token.
- Convert Confluence storage body to markdown.
- Preserve page-id-prefixed filenames.
- Preserve classifier-owned fields across re-sync.
- Store observed schema-v2 fields:
  - `word_count`
  - `char_count`
  - `token_estimate`
  - `attachment_count`
  - `tags_original`
  - `visibility_signal`
  - `restriction_check`
  - `restricted_to`
- Keep existing compatibility fields:
  - `labels`
  - `audience`
  - `doc_type`
  - `tools`
  - `topics`
  - `days_since_modified`
  - `maintenance_signal`
  - `conversion_warnings`

Not yet implemented:

- Direct page restriction checks.
- Ancestor/folder restriction checks.
- Inherited restriction classification.
- Detailed access manifest.
- Public-only MCP indexing/query filtering.
- Upstream attachment metadata beyond locally mirrored `attachment_count`.
- Additional API-owned page/folder fields such as `createdAt`, `authorId`, `ownerId`, `parentId`, and `position`.

## Live API Probe Findings

Probe date: 2026-05-19, using the local Confluence Cloud API token from `.env`.

### Space Metadata

The ITSAI space endpoint returns:

```yaml
id
key
name
type
status
homepageId
authorId
spaceOwnerId
createdAt
currentActiveAlias
description
icon
```

Observed:

```yaml
key: ITSAI
name: Artificial Intelligence (AI)
type: knowledge_base
status: current
homepageId: '483525103'
```

### Page Metadata

The v2 page list/detail endpoints return:

```yaml
id
status
title
spaceId
parentId
parentType
position
authorId
ownerId
lastOwnerId
createdAt
version:
  number
  message
  minorEdit
  authorId
  createdAt
  ncsStepVersion
body:
  storage
labels
_links
```

These are API-owned facts and should be preferred over local inference where useful.

### Folder Metadata

The v2 folder endpoint returns:

```yaml
id
title
type
status
spaceId
parentId
parentType
position
authorId
ownerId
lastOwnerId
createdAt
version
_links
```

Folder metadata matters because Confluence page restrictions can be inherited from ancestor folders.

### Ancestor Metadata

The v2 page ancestors endpoint returns ancestor IDs and types:

```yaml
ancestors:
  - id
    type
```

Titles often require follow-up calls to `/pages/{id}` or `/folders/{id}`. The puller already does this for folder-path reconstruction.

### Labels

Labels are available either inline from `GET /pages/{id}?include-labels=true` or via:

```text
GET /wiki/api/v2/pages/{page_id}/labels
```

Shape:

```yaml
results:
  - id
    name
    prefix
meta:
  hasMore
  cursor
_links
```

Observed ITSAI labels are sparse; most pages have none.

### Attachments

The v2 page attachments endpoint returns:

```yaml
id
status
title
createdAt
pageId
mediaType
mediaTypeDescription
comment
fileId
fileSize
webuiLink
downloadLink
version:
  number
  message
  minorEdit
  authorId
  createdAt
labels
operations
_links
```

Possible future API-backed fields:

```yaml
upstream_attachment_count
upstream_attachment_bytes
attachment_media_types
```

Keep current `attachment_count` semantics as "attachments successfully mirrored locally" unless renamed.

### Versions

Current page version metadata is returned inline on page detail. Historical versions are available through:

```text
GET /wiki/api/v2/pages/{id}/versions
GET /wiki/api/v2/pages/{id}/versions/{version_number}
```

Version detail includes:

```yaml
number
authorId
message
createdAt
minorEdit
contentTypeModified
collaborators
prevVersion
nextVersion
```

Historical bodies can be fetched through v1 when needed:

```text
GET /wiki/rest/api/content/{id}?version=<n>&expand=body.storage,version
```

For edit-cadence reporting, version metadata is enough. Historical bodies should be fetched only for explicit diff/audit workflows.

## Access Metadata Observations

### Direct Restrictions

The v1 restriction endpoint works against both pages and folders:

```text
GET /wiki/rest/api/content/{id}/restriction/byOperation
```

It returns operation buckets such as:

```yaml
read:
  restrictions:
    user:
      results: [...]
    group:
      results: [...]
update:
  restrictions:
    user:
      results: [...]
    group:
      results: [...]
```

The exact user/group object shape should be treated as raw API data for now. Do not invent a normalized schema until implementation confirms the response shape across more pages.

### Summer Intern 2026 Finding

The Summer Intern child pages themselves showed no direct read/update restrictions:

```yaml
direct_page_read_user_count: 0
direct_page_read_group_count: 0
direct_page_update_user_count: 0
direct_page_update_group_count: 0
```

Their parent folder `1069121551 - Summer Intern 2026` showed direct folder restrictions:

```yaml
direct_folder_read_user_count: 4
direct_folder_read_group_count: 0
direct_folder_update_user_count: 4
direct_folder_update_group_count: 0
```

Normal comparison folders such as `AI` and `Claude` showed zero direct read/update restrictions.

Conclusion: page-only restriction checks are insufficient. Phase 1.1 must walk the ancestor chain and check restrictions on every page/folder ancestor.

## Access Model For Phase 1.1

Do not solve per-user RBAC yet. Classify pages into conservative visibility buckets from configured Confluence restrictions.

Recommended coarse values:

```yaml
visibility_signal: no_read_restrictions_seen
visibility_signal: restricted_direct
visibility_signal: restricted_inherited
visibility_signal: unknown
```

Definitions:

- `no_read_restrictions_seen`: page and all ancestors returned successfully, and no direct `read` restrictions were found on the page or ancestor chain.
- `restricted_direct`: the page itself has a non-empty direct `read` restriction.
- `restricted_inherited`: at least one ancestor page/folder has a non-empty direct `read` restriction.
- `unknown`: any restriction check failed, returned an unexpected shape, or could not be completed.

Avoid `public` unless tested with a truly public/anonymous or low-privilege principal. In SU Confluence, the practical v1 audience is "general SU-accessible," not necessarily internet-anonymous.

## Where Metadata Should Live

Use two canonical stores.

### 1. Markdown Frontmatter

Keep frontmatter small and useful for humans, debugging, and coarse MCP routing.

Recommended additions or updates:

```yaml
visibility_signal: no_read_restrictions_seen | restricted_direct | restricted_inherited | unknown
restriction_check: checked_direct_and_ancestors | failed | not_checked
restriction_source_ids:
  - '1069121551'
```

Optionally add more API-owned page facts if useful for backend management:

```yaml
created_at
author_id
owner_id
last_owner_id
parent_id
parent_type
position
```

Do not put full user/group allowlists in page frontmatter by default.

### 2. Access Manifest

Detailed access data belongs in a backend manifest keyed by `page_id`:

```text
output/_access/access-manifest.jsonl
```

One JSON object per page:

```json
{
  "page_id": "1068171339",
  "title": "Julian Test 1st Page",
  "space_key": "ITSAI",
  "visibility_signal": "restricted_inherited",
  "restriction_check": "checked_direct_and_ancestors",
  "checked_at": "2026-05-19T00:00:00Z",
  "checked_with_principal": "sync_user",
  "direct_read_restrictions": {
    "has_restrictions": false,
    "user_ids": [],
    "group_ids": [],
    "raw": {}
  },
  "direct_update_restrictions": {
    "has_restrictions": false,
    "user_ids": [],
    "group_ids": [],
    "raw": {}
  },
  "inherited_read_restrictions": [
    {
      "source_id": "1069121551",
      "source_type": "folder",
      "source_title": "Summer Intern 2026",
      "user_ids": ["..."],
      "group_ids": [],
      "raw": {}
    }
  ],
  "errors": []
}
```

Implementation may start with counts and raw response snapshots if stable ID extraction is not immediately clean. Counts are debugging signals only; they are not enough for future enforcement.

## MCP Behavior

### V1 General MCP

The v1 MCP should only query pages classified as:

```yaml
visibility_signal: no_read_restrictions_seen
```

Apply this to every retrieval surface:

- `search`
- `get_page`
- `list_index`
- `list_hubs`
- citation/page resolution

Do not rely on prompt instructions alone. Tool code should enforce this filter.

### Future Admin/User-Aware MCP

Future enforcement can use:

```text
user identity from MCP auth
user groups from an identity/group lookup
access-manifest.jsonl or database table
page_id join key
```

Then filter results by intersection between the user's account/group IDs and the page's direct/inherited allowlists.

Do not make live Confluence permission checks on every search unless there is no alternative; that will likely be too slow and brittle.

## Phase 1.1 Implementation Plan

### Step 1 - Standalone Probe/Classifier

Before wiring into the puller, create a read-only script:

```text
scripts/access_metadata_probe.py
```

Inputs:

```text
--space ITSAI
--page-id <optional repeated page id>
--out output/_access/access-manifest.jsonl
--summary output/_access/access-summary.md
```

Behavior:

1. Load Confluence credentials from `.env` or environment.
2. For each page:
   - fetch page metadata
   - fetch ancestor chain
   - resolve ancestor titles/types
   - fetch direct page restrictions
   - fetch direct ancestor restrictions
   - compute `visibility_signal`
   - write one manifest record
3. Write a summary grouped by:
   - `no_read_restrictions_seen`
   - `restricted_direct`
   - `restricted_inherited`
   - `unknown`

Acceptance check:

- Summer Intern pages classify as `restricted_inherited`.
- Normal AI/Claude pages classify as `no_read_restrictions_seen`.
- Any endpoint error classifies as `unknown`, not unrestricted.

### Step 2 - Puller Integration

After the standalone probe shape is validated, integrate the same logic into `src/sukb/ingest/puller.py`.

Per page:

1. Fetch metadata first as currently designed.
2. Resolve ancestors.
3. Check direct page restrictions.
4. Check ancestor restrictions.
5. Compute coarse `visibility_signal`.
6. Write coarse fields to frontmatter.
7. Append detailed record to `output/_access/access-manifest.jsonl`.
8. Continue writing the full markdown body for every page visible to the sync user.

Keep the access manifest append/update deterministic. Prefer writing a complete manifest per sync instead of appending duplicate stale records forever.

### Step 3 - MCP/Indexer Filtering

Update the chat/MCP retrieval layer so the general v1 surface only indexes or returns page IDs whose access record says:

```yaml
visibility_signal: no_read_restrictions_seen
```

If a page has no manifest record, default to exclude.

### Step 4 - Tests

Add tests for:

- page with no restrictions -> `no_read_restrictions_seen`
- page with direct read restriction -> `restricted_direct`
- page with restricted ancestor -> `restricted_inherited`
- restriction endpoint failure -> `unknown`
- MCP/indexer excludes restricted/unknown pages
- manifest records are keyed by `page_id`
- Summer Intern fixture behavior, using synthetic API fixtures rather than live Confluence

## Non-Goals

Do not implement these in Phase 1.1:

- per-user runtime RBAC
- group membership resolution
- student/admin account comparison
- live Confluence permission checks during MCP query
- raw folder restructure such as `raw/public/` and `raw/internal/`
- deleting or quarantining restricted markdown bodies
- putting human-readable names/emails in frontmatter
- treating `visibility_signal` as the final security boundary

## Open Questions

1. Does the restriction endpoint consistently return stable group IDs/user account IDs for all restricted content Julian can read, or only counts/expandable links in some cases?
2. Can space-level default access be classified reliably through the available API, or should Phase 1.1 only classify page/folder restrictions and label space-level access as `space_scope_unchecked`?
3. Should detailed raw restriction API responses be stored in the manifest, or should the manifest store only normalized IDs plus an error/debug summary?
4. Should `output/_access/` be committed, or generated locally during ingest and excluded from git once the project moves toward production?
5. Should public-only indexes be generated under `output/_views/public/`, or should MCP tools filter full indexes at read time?

## Current Recommendation

For the next development session:

1. Do not reopen Phase 1.
2. Write `scripts/access_metadata_probe.py` first.
3. Validate it against ITSAI, especially `Summer Intern 2026`.
4. Use the probe output to finalize the manifest shape.
5. Only then wire access classification into the puller and MCP/indexing layer.

This keeps the current folder architecture intact while adding the access metadata needed for a production-grade MCP path.
