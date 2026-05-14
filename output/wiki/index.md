---
title: "Wiki Index — SU AI Knowledge Base Hubs"
type: index
status: reviewed
synthesizes: []
created: 2026-05-14
updated: 2026-05-14
reviewer: jlhernan@syr.edu
tags:
  - index
  - wiki
  - navigation
---

# Wiki Index — SU AI Knowledge Base Hubs

LLM-drafted, human-reviewed synthesis hubs for questions that no single raw page can answer well on its own. Every hub cites raw pages via `[[<page-id>]]`. If a question can be fully answered from one raw page, prefer the raw page — don't route through a hub.

Rules for what counts as a hub and how they're maintained: see [`../../research/kb-ingestion-project/wiki-operating-model.md`](../../../research/kb-ingestion-project/wiki-operating-model.md).

## Hubs

### `approved-ai-tools-for-university-data.md` — Approved AI Tools at Syracuse: Data Policy & Capability Comparison

**Status:** reviewed
**Synthesizes:** 8 raw pages — `488144948` (Approved Tools list), `488210484` (Claude FAQ), `522289260` (Copilot FAQ), `498597967` (Gemini FAQ), `483525103` (AI @ SU landing), `544538648` (Gemini @ SU), `534642749` (Claude Enterprise @ SU), `544505857` (mentorAI @ SU)

**When to use this hub:**
- "Which approved AI tools can I use with FERPA / Confidential / [classification] data?"
- "How long does Claude vs. Copilot vs. Gemini retain my chats? Do any of them train on my data?"
- "Who owns the outputs I generate in Claude / Copilot / Gemini?"
- Any policy comparison across multiple approved tools.

**Why prefer this over raw pages:** The Approved Tools list page is link-only and each per-tool FAQ only covers one platform. This hub is the side-by-side comparison the corpus otherwise doesn't have.

---

### `claude-at-syracuse-product-surface-map.md` — Claude at Syracuse: Product Surface Map

**Status:** reviewed
**Synthesizes:** 10 raw pages — every Claude surface (`534642749`, `522158118`, `540934169`, `836698117`, `544210961`, `841875458`, `837517313`, `988774401`, `986841103`, `488210484`)

**When to use this hub:**
- "What's the difference between Claude Chat, Claude Code, Cowork, and MCP — and which can I actually use at SU?"
- "How do I connect Claude to SharePoint / Power BI / [other tool]?"
- "Why is Claude Cowork disabled at SU and what should I use instead?"
- Any question about which Claude surfaces are enabled, cost extra, or are disabled at SU.

**Why prefer this over raw pages:** The "what's enabled vs disabled" status table doesn't exist on any single raw page — it requires synthesis across 10. Also serves as a demoable canonical artifact for the broader Claude story at SU.

## When NOT to use a hub

- The question is about one specific page or one specific topic that has a strong dedicated raw page (e.g., "how do I install Claude Code on Windows" → the Claude Code Setup raw page is better than any hub).
- The question is procedural how-to (the hubs are policy/synthesis-flavored, not step-by-step).
- The user explicitly asks for the source page.

## Hub discipline (quick reference)

- Minimum 3 raw pages synthesized — no 1:1 rewrites.
- Every factual claim cites `[[<page-id>]]` inline.
- `status: draft` → `reviewed` (human-promoted) → `evergreen` (lint-validated) → `deprecated` (kept for backlink stability).
- Only `reviewed` and `evergreen` hubs are loaded by `sukb.chat.query.load_wiki_corpus`.
- Full rules in [`wiki-operating-model.md`](../../../research/kb-ingestion-project/wiki-operating-model.md).

## Proposing new hubs

Run `scripts/run_proposals.py` against the corpus. It produces a candidate list with `addresses_eval_queries`, `synthesizes`, `leverage` fields. Human curates which to build. The Step 4 output from 2026-05-13 lives at `../../research/kb-ingestion-project/wiki-proposals-2026-05-13.md`.
