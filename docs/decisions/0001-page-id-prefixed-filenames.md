---
status: accepted
date: 2026-05-09
supersedes:
---

# 0001. Page-ID-prefixed filenames

## Context

The ingest pipeline writes one Markdown file per Confluence page. The filename has to satisfy four constraints simultaneously:

1. **Collision-safe across spaces.** Two different SU spaces (ITSAI, ITHELP, CDIAPPS, etc.) can have pages with the same title. A flat filename like `Claude FAQ.md` would collide.
2. **Rename-safe in Confluence.** SU staff can rename a Confluence page at any time; downstream consumers (wikilinks in other pages, our sync state, future indexers) shouldn't break when that happens.
3. **Deterministic wikilink resolution.** When page A links to page B via `<ac:link>` in Confluence storage XML, the converter needs to emit a canonical Markdown reference that always resolves to the right file — even if B's title later changes.
4. **Parseable.** The converter needs to extract the page_id from any filename in `output/raw/` without parsing frontmatter (cheap directory scans for `.sync-state.json` recovery, for indexing, for the chat layer's corpus loader).

Confluence's own page IDs are stable, unique, and numeric. They satisfy all four constraints. Page titles do not.

## Decision

Every converted page is named `<page-id> - <sanitized-title>.md`. Examples:

- `488210484 - Claude - Frequently Asked Questions.md`
- `986841103 - Claude Code Setup.md`

The page ID is the load-bearing identifier; the title is human-readable affordance. Wikilinks in converted output follow the same pattern: `[[<page-id> - <title>]]` (Obsidian-flavored, in-corpus references) or `[<title>](search_url)` (out-of-corpus references that still need to be readable).

Title sanitization strips Windows-illegal characters (`<>:"/\|?*`) per the matching spec section. Em-dashes and en-dashes are preserved (they show up frequently in SU page titles).

## Consequences

**Positive:**

- Same-title pages in different spaces don't collide.
- Confluence renames don't cascade into broken local files or broken wikilinks — the page ID still resolves.
- The converter and chat-layer corpus loader can extract `page_id` via a single regex on the filename. No frontmatter read required for routing.
- Citations from the chat layer (`[[488210484]]`) are stable, machine-checkable references back to source. The eval scoring and any future audit pipeline can verify them deterministically.
- Wikilinks become a real graph: every edge has a stable endpoint, so the corpus can be traversed by an agentic model the same way it'd traverse a workspace.

**Negative / trade-offs accepted:**

- Filenames are uglier than pure titles. The page-ID prefix is visible in folder listings, in Obsidian, in any UI that shows raw filenames. Acceptable cost: the alternative is silent corruption when collisions or renames happen.
- The Markdown isn't a 1:1 lift of what Confluence shows. Users who want "the original" need to follow `source_url` in the frontmatter.

## Alternatives considered

- **Human-readable filename + page_id in `aliases:` frontmatter field.** Cleaner visually, but breaks constraint 4 (cheap parsing) and makes wikilink resolution depend on a frontmatter scan of every file. Rejected.
- **Slugified title only (e.g., `claude-faq.md`).** Breaks constraints 1 and 2. Rejected.
- **Hash of `(space, title)` as filename.** Stable but completely unreadable; no human can navigate the folder. Rejected.
