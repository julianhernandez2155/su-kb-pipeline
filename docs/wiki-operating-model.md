---
title: Wiki Operating Model
status: draft v0.1
date: 2026-05-13
project: kb-ingestion-internship
companion: [pipeline-spec.md](pipeline-spec.md) §4.7, [pipeline-spec-proposals.md](pipeline-spec-proposals.md), [v1-tool-brief.md](v1-tool-brief.md)
inspired-by: Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (Apr 2026)
---

# Wiki Operating Model

The rules that govern the `wiki/` synthesis layer at SU. Read this **before** writing or accepting any wiki article into the corpus.

---

## 1. The non-negotiable: source of truth

> **Confluence is the authoritative source of truth.**
> **`raw/` is the immutable mirror of Confluence.**
> **`wiki/` is an LLM-drafted, human-reviewed synthesis layer where every claim cites raw page IDs back to authoritative source.**

Unlike Karpathy's personal-notes LLM-Wiki pattern — where the LLM owns synthesis entirely because there's no third-party authority — the SU instance has:

- Confluence pages owned by SU departments, not by the EDA team
- Institutional liability if the wiki drifts from authoritative source
- A user expectation that "what the AI said" can be traced back to "what the policy actually says"

The wiki must never become a free-floating second source. Every wiki claim has a clickable trail back to one or more raw pages.

## 2. The litmus test (from spec §4.7)

> *If a proposed wiki article is just one raw page reworded, don't make it.
> If it stitches across **3+ raw pages**, make it.*

A wiki article exists because it captures a view that **no single raw page owns**. Examples that pass:

- **`approved-ai-tools-for-university-data.md`** — synthesizes Claude FAQ + Copilot FAQ + Gemini FAQ + Approved Tools list + Data Privacy policy
- **`data-classification-across-tools.md`** — pulls from Information Security Standard + per-tool privacy notes + Vendor AI Policy
- **`mcp-and-connectors-at-syracuse.md`** — Claude Local MCP + Connectors + Phase B service plan + ITS guidance

Examples that fail (do not write):

- `wiki/Claude FAQ.md` — 1:1 with `raw/.../Claude FAQ.md`. Redundant. Enrich raw instead.
- `wiki/mentorAI Settings & Options.md` — same. The raw page is the answer.

## 3. Authorship rules

| Rule | Reason |
|---|---|
| **LLM drafts, human promotes.** A wiki article enters `wiki/` only after a named human (intern or staff) reviews and accepts it. | Catches hallucination, drift, missing nuance, sensitive content the LLM didn't know to handle. |
| **Every major claim cites at least one raw page ID.** Format: `[[<page-id> - <title>]]`. | The clickable trail back to authoritative source is mandatory, not decorative. |
| **No claims without source.** If the LLM wants to say something the raw corpus doesn't support, that's a gap to flag — not content to invent. | Wiki ≠ original research. |
| **No 1:1 rewrites of raw pages.** If a hub would synthesize fewer than 3 raw pages, write the hub anyway only if it captures structure the raw can't (e.g., a comparison matrix). Otherwise reject. | Avoids index pollution and content drift. |
| **Frontmatter declares synthesis sources explicitly.** A `synthesizes:` list in YAML lists every raw `page_id` the article draws from. | Makes drift detection mechanizable — a future lint pass can verify all claims still have sources. |

## 4. Wiki article frontmatter

Lighter than `raw/` (no Confluence-mirrored metadata):

```yaml
---
title: "Approved AI Tools for University Data"
type: hub
status: draft | reviewed | evergreen | deprecated
synthesizes:                      # explicit list of raw page_ids this hub draws from
  - "488210484"                   # Claude FAQ
  - "522289260"                   # Copilot FAQ
  - "498597967"                   # Gemini FAQ
  - "488144948"                   # Approved Tools list
created: 2026-05-13
updated: 2026-05-13
reviewer: jlhernan@syr.edu        # who promoted this from draft to reviewed
tags:
  - hub
  - ai-policy
---
```

Fields required:

| Field | Purpose |
|---|---|
| `type: hub` | Distinguishes wiki articles from any other kind of synthesis (always `hub` in v1.5). |
| `status` | `draft` → LLM proposed, human not yet reviewed. `reviewed` → human accepted into wiki. `evergreen` → confirmed accurate after a lint pass. `deprecated` → kept on disk for backlink stability but excluded from search. |
| `synthesizes: [<page_id>, ...]` | The raw pages this article draws from. Used by the lint pass to detect drift. Minimum 3 entries. |
| `reviewer` | The human who promoted this article. Accountability matters. |
| `created` / `updated` | Track wiki staleness independently of raw staleness. |

## 5. Workflow: how a wiki article gets written

```
[1] LLM proposes (Karpathy-style ingest pass)
       │
       ▼
[2] Candidate list  ──→  Human curator picks promising ones
       │
       ▼
[3] LLM drafts with citations  ──→  human reviews
       │                              │
       │                       (reject) — back to draft, or kill
       │                              │
       ▼                              ▼
[4] Promote to wiki/  ←─────  (accept)
       │
       ▼
[5] Periodic lint  ──→  flag drift, orphans, broken citations
```

**Step 1 — Proposal pass.** Once per significant raw-corpus update (or quarterly), an LLM reads `raw/<space>/*.md` and proposes wiki hub candidates. Output is a structured list, not pages:

```yaml
- title: "Approved AI Tools for University Data"
  why_it_exists: "Cross-cuts the per-tool FAQs and the approved-tools policy"
  synthesizes: ["488210484", "522289260", "498597967", "488144948"]
  example_queries: ["Can I use Claude with FERPA data?", "What AI tools work with grade data?"]
- title: "..."
  ...
```

**Step 2 — Curator picks.** A human looks at the candidate list. Accepts the obvious ones. Rejects 1:1-with-raw candidates. Marks borderline cases for further investigation.

**Step 3 — LLM drafts.** For each accepted candidate, LLM writes the actual article — synthesis with mandatory `[[<page-id> - <title>]]` citations.

**Step 4 — Human review + promotion.** Reviewer reads the draft, checks every citation resolves to a real page that actually supports the claim. On accept, promotes from `draft` to `reviewed`, sets `reviewer`. On reject, kills or sends back.

**Step 5 — Periodic lint.** A scheduled LLM pass scans the wiki for:

- Citations whose target page no longer exists in raw
- Citations whose target page's `last_modified` is newer than the wiki article's `updated` (stale signal)
- Claims that have no citation (forbidden)
- Orphan wiki articles (no `[[wikilink]]` from any other wiki article — may indicate the topic doesn't fit the synthesis pattern)
- Contradictions across wiki articles (e.g., two hubs assert different policy on the same topic)

Lint output is a triage list, not auto-fix. A human decides what to update, deprecate, or merge.

## 6. What the wiki is NOT

To save argument later:

- **Not a help system.** It does not contain instructional content not present in raw. If a how-to needs to exist, the raw Confluence page is the place to write it.
- **Not opinionated.** No editorial voice. Articles describe what the raw corpus says.
- **Not a chatbot transcript.** Wiki articles are stable, dated, reviewed. Conversational answers from MCP are ephemeral by design.
- **Not version-controlled per article.** The whole `wiki/` lives in git (when the project moves to a repo); fine-grained diff per article is not a workflow we maintain.
- **Not multi-author within a single article.** One reviewer per article at a time. If two people disagree about a claim, deprecate and rewrite — don't co-edit.

## 7. Open questions (resolve before Phase 2)

1. **Promotion authority.** v1.5 has Julian + interns as reviewers. Phase 2 (other spaces) — does ITS staff own wiki articles in their domain? Per-domain reviewer assignment?
2. **Deprecation policy.** If a raw page is deleted from Confluence and a wiki article cites it, what's the workflow? Auto-deprecate the wiki article? Re-cite to a replacement? Manual review?
3. **Conflict between wiki articles and raw.** If a wiki synthesis contradicts what a raw page newly says (raw was edited after wiki was reviewed), which wins? Default: raw is source of truth → flag the wiki article as `draft` again and re-review.
4. **Wiki layer for non-public content.** Public-at-SU only in v1.5. When non-public Confluence content enters scope, does the wiki layer also get NetID-filtered? Probably yes, but the implementation is downstream of MCP auth.
5. **Linguistic surface.** Wiki articles in English only? When SU's multilingual content surfaces, do we synthesize across languages or maintain per-language hubs?

## 8. References

- [`pipeline-spec.md`](pipeline-spec.md) §4.7 — sparse wiki layer, original spec for this layer
- [`v1-tool-brief.md`](v1-tool-brief.md) §5 — the SU caveat that shaped these rules
- [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — original pattern this adapts
- [`pipeline-spec-proposals.md`](pipeline-spec-proposals.md) — pending v0.5+ spec proposals, some of which (lint loop, query feedback) feed into this document
