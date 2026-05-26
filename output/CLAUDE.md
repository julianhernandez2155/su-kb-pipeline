# SU AI Knowledge Base — Agent Rules

This `output/` tree is the converted form of Syracuse University's AI Knowledge Base. It is the corpus a Claude-based MCP server will surface to students and faculty. Read this file first when working with anything in this tree.

## What's here

```
output/
├── CLAUDE.md           ← you are here (rules)
├── index.md            ← global map: spaces + wiki + how to navigate
├── raw/                ← immutable Confluence mirror (source of truth)
│   └── knowledge-bases/
│       └── Artificial Intelligence (AI)/
│           ├── index.md   ← space-level routing
│           └── <page-id> - <title>.md   (× 29 public; restricted pages exist on disk but are filtered out of every chat/agentic surface)
├── wiki/               ← LLM-drafted, human-reviewed synthesis hubs
│   ├── index.md           ← hub map
│   ├── approved-ai-tools-for-university-data.md
│   └── claude-at-syracuse-product-surface-map.md
├── _access/            ← access-classification artifacts (Phase 1.1, ADR-0007)
│   ├── access-summary.md   ← committed, sanitized rollup (counts + folder-source names only)
│   ├── access-manifest.jsonl  ← gitignored — per-page PII (account IDs, raw API)
│   └── spaces.json     ← gitignored — per-space audience cache, paginated raw
├── query-sessions/     ← saved Query-tab chats (eval artifacts; not corpus)
└── conversion-failures/  ← dead-letter pages (not corpus)
```

## The two-layer model

### `raw/` is the source of truth

- Mirrors Confluence pages 1:1. Every file is named `<page-id> - <sanitized-title>.md`.
- **Never edit pages in `raw/`.** If a fact is wrong, fix it in Confluence and re-run the pull.
- The page-ID prefix is load-bearing: collision-safe across spaces, rename-safe in Confluence, lets wikilinks resolve deterministically.

### `wiki/` is LLM-drafted, human-reviewed synthesis

- Each hub captures a cross-cutting view no single raw page owns.
- **Every factual claim cites at least one raw page** via `[[<page-id>]]` inline at the end of the sentence. Example: `Claude retains chats for 2 years [[488210484]].`
- Hubs synthesize **3+ raw pages**. If a candidate hub would be a 1:1 rewrite of a single raw page, reject it.
- Each hub has a `status` field: `draft` → `reviewed` → `evergreen` → `deprecated`. Only `reviewed` and `evergreen` count as part of the queryable corpus.
- **Hubs whose `synthesizes:` references a restricted raw page are dropped entirely at load time** ([ADR-0009](../docs/decisions/0009-mcp-read-path-filter.md)). Partial filtering is unsafe — the hub body may paraphrase or cite the restricted source.
- Full operating rules: see [../docs/wiki-operating-model.md](../docs/wiki-operating-model.md).

### `_access/` is the access-classification artifact tree (Phase 1.1)

The puller writes three files per sync under `_access/` (see [ADR-0007](../docs/decisions/0007-access-classification-v1.md)):

| File | Tracked? | Contents |
|---|---|---|
| `access-summary.md` | ✅ committed | Human-readable rollup: counts by `visibility_signal`, layers checked, folder-source names that gate access. Sanitized — never carries restricted-page titles, account IDs, or emails. |
| `access-manifest.jsonl` | ❌ gitignored | One line per page: full classification record, including normalized `read.user_ids` + `read.group_ids` + raw API payload. **Carries PII** (account IDs, sometimes emails). Treat like `.env`. |
| `spaces.json` | ❌ gitignored | Per-space audience cache, paginated raw permissions. Includes group IDs. Re-parseable for future classifier tightening. |

**Agent rules for `_access/`:**

- **Inspection-only.** Read these to debug ingest health or understand why a page was filtered — never copy their contents into a chat answer or wiki hub.
- **`access-summary.md` is safe to reference in commit messages, ADRs, and STATUS.md** (it's sanitized). Use it when reporting "the 3 Summer Intern pages classify as `restricted_inherited` via folder `1069121551`" — that's exactly the kind of fact the summary exists to surface.
- **`access-manifest.jsonl` and `spaces.json` MUST NOT be exposed via any user-facing surface.** They're admin/dev-tier per [ADR-0010](../docs/decisions/0010-trust-zones-admin-vs-mcp.md). If you need to reason about their contents in code, the data flow is: puller → manifest → MCP filter at `load_raw_corpus` reads `visibility_signal` from frontmatter (not the manifest).
- **Don't hand-edit any file in `_access/`** — they're regenerated on every puller run. Hand-edits are lost on next sync. Sanitization rules in [ADR-0007 §"Sanitization audit"](../docs/decisions/0007-access-classification-v1.md).

## Citation discipline (applies to anything you write or quote from this corpus)

- Inline `[[<page-id>]]` or `[[<page-id> - <title>]]` is the canonical citation form.
- If a claim has no support in the corpus, **drop it** — don't invent.
- If a wiki hub claim cites a page outside its own `synthesizes:` list, that's a bug — either add the page to `synthesizes:` or remove the claim.
- The trailing `Sources:` line in an answer is summary, not authoritative. The inline `[[pid]]` markers are.

## Navigation pattern

You're not expected to read the whole corpus. Read orientation files first, drill down only as needed.

1. **Start at `index.md`** — figure out which space and whether a wiki hub already covers your question.
2. **For a specific space**, read its space-level `index.md` to find the relevant subcategory.
3. **For cross-cutting questions** (policy comparison, tool selection, MCP/connectors map), check `wiki/index.md` first — a hub may already synthesize the answer.
4. **Follow `[[<page-id>]]` wikilinks** when a page references another. Treat them as graph edges, not decoration.

This is the same pattern Claude Code uses in a workspace: orient via `CLAUDE.md`/`index.md`, drill down via search and reads, follow references.

## Adding a new wiki hub

1. Confirm it synthesizes ≥3 raw pages and is not a 1:1 rewrite. If unsure, run a proposal pass against the corpus before drafting.
2. Frontmatter must include: `title`, `type: hub`, `status: draft`, `synthesizes: [<page_ids>]`, `created`, `updated`, `tags`. Set `reviewer:` only when promoting to `reviewed`.
3. Body must cite every claim with `[[<page-id>]]`.
4. End with a `## Sources` section listing every raw page cited as `[[<page-id> - <title>]]`.
5. Add a one-line entry to `wiki/index.md` describing when this hub applies.

## What this corpus is NOT

- **Not a help system.** Instructional how-tos live in raw Confluence pages, not in the wiki.
- **Not opinionated.** Wiki hubs describe what the corpus says, not what the EDA team thinks is best.
- **Not a chatbot log.** Saved query sessions live in `query-sessions/`, separate from the corpus.
- **Not version-controlled per-page.** The whole `output/` is the artifact; we don't maintain page-level history beyond Confluence itself.
