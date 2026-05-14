---
title: SU KB Ingestion Tool — v1 Brief
status: deliverable
date: 2026-05-13
author: Julian Hernandez (with Claude + Codex review)
audience: Aaron Starr, Andrew Joncas; intern cohort (Shahaan, Robert)
project: kb-ingestion-internship
companion: [pipeline-spec.md](pipeline-spec.md) v0.4, [pipeline-spec-proposals.md](pipeline-spec-proposals.md), [v1-prototype-plan.md](v1-prototype-plan.md)
implements: pipeline-spec.md v0.4 §§4.1–4.6
---

# SU KB Ingestion Tool — v1 Brief

## TL;DR

We built and validated the first slice of the SU Knowledge Base ingestion pipeline against Confluence's **Artificial Intelligence (AI)** workspace (`ITSAI`, 34 current pages). The tool pulls a Confluence space via API, converts every page to clean Obsidian-flavored Markdown, downloads attachments, verifies on-disk integrity, and surfaces the whole pipeline through an IT-admin web UI. All 34 ITSAI pages convert cleanly with zero failures and zero warnings; 64 attachments (~21 MB) are downloaded and verified; re-running the pull is a 1.5-second no-op via content-hash skip. The pipeline is one config change away from supporting any other Confluence space at SU.

This is the **raw layer** of the architecture from [`pipeline-spec.md`](pipeline-spec.md) §2: source-of-truth Markdown mirroring Confluence. The next phase is a **wiki layer** — LLM-drafted, human-curated synthesis pages with citations back to raw — plus a chat-style query surface to validate that the corpus answers real student/staff questions. That work is queued and scoped, not yet built.

---

## 1. What we built

**A. A Python package — `kb_ingest/`** — that pulls a Confluence space via the v2 REST API and writes a structured Markdown corpus to disk. Modular by design: each pipeline stage (pull, convert, link-resolve, attachments, frontmatter, dead-letter, state) lives in its own file, so the downstream FTS5 indexer and MCP server can reuse the modules unchanged.

**B. A FastAPI service** — that exposes the pipeline operationally: list spaces, kick off a pull, stream live progress events, browse converted output, inspect dead-lettered failures, view sync state. Same backend code is available to future programmatic callers and to the UI.

**C. An IT-admin web UI** — dense, four-tab interface (Pull / Output / Failures / Config) styled for the "ops console" shape, not consumer polish. Click a space, watch 34 pages convert in real time, drill into any converted file for source-vs-output side-by-side, retry failures with a button.

**D. A 75-test suite** — one test per macro handler, one per ADF node type, plus integration tests covering frontmatter validation, sync-state roundtrips, the three-knob inclusion logic, attachment verification, and the seven visual-QA regression fixes from the post-conversion walkthrough.

**Repo location:** [`prototypes/confluence-to-md-v2/`](../../prototypes/confluence-to-md-v2/). Sibling to the original v0 prototype (`confluence-url-to-markdown/`), which is preserved as a reference but unmodified.

## 2. How it works

The pipeline is **eight stages**, each isolated:

```
Confluence (via Atlassian Gateway)
        │
        ▼
[1] Pull        — list pages with bodies + ancestors + labels + attachments
[2] Convert     — storage XML → Markdown; macros + ADF + wikilinks + images
[3] Verify      — every emitted attachment reference must exist on disk
[4] Frontmatter — §4.4 schema; classifier fields null until v1.1
[5] State       — per-page content_hash + version → skip on rerun
[6] Dead-letter — failures routed to conversion-failures/, never to raw/
[7] Surface     — FastAPI streams progress events via SSE
[8] UI          — four-tab admin console
```

**Output shape:**

```
output/raw/
└── knowledge-bases/                 ← curatorial category (from sync_config.yaml)
    └── Artificial Intelligence (AI)/
        ├── .meta/                   ← sync-state.json, space-manifest.json, sync-log.jsonl
        ├── 483525103 - AI @ Syracuse University.md
        ├── (Test) Resume Tailor Machine Brain/
        │   └── 965672963 - The Workflow (how you actually use it).md
        ├── AI @ Syracuse University/
        │   ├── AI/
        │   │   ├── Claude/
        │   │   │   ├── 488210484 - Claude - Frequently Asked Questions.md
        │   │   │   ├── Example Uses/
        │   │   │   └── ... (10 more)
        │   │   ├── Clementine Platform/ (6 pages)
        │   │   ├── Copilot/ (1)
        │   │   ├── Gemini/ (4)
        │   │   └── AI - General Information/ (2)
        │   └── Summer Intern 2026/ (3 — Julian/Shahaan/Robert test pages)
        └── attachments/
            ├── 483525103/Screenshot 2026-03-10 203239.png
            ├── 986841103/Install-DevTools.ps1
            └── ... (62 more)
```

Filenames are `<page-id> - <sanitized-title>.md` — the page-id prefix is load-bearing for collision-safety, rename-safety, and deterministic wikilink resolution.

**One worked example** — a converted page with frontmatter, callouts, wikilinks, attachments, and a code block:

```markdown
---
page_id: '986841103'
title: Claude Code Setup
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/986841103/...
space_key: ITSAI
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path: [AI @ Syracuse University, AI, Claude]
last_modified: '2026-04-22T15:47:11.293Z'
version: 17
contributors_count: 3
content_hash: sha256:a3f2c8...
synced_at: '2026-05-13T16:41:34Z'
labels: [claude-code, setup]
days_since_modified: 21
maintenance_signal: fresh
audience: null               ← populated by v1.1 classifier
doc_type: null               ← populated by v1.1 classifier
---

# Step 1: Get access to Claude Code

Using one of the methods on [[540934169 - Purchase Claude Code and Claude API Access|Purchase Claude Code]]…

| **Tool** | **Version** | **Notes** |
| --- | --- | --- |
| Node.js | 24.12.0 | Portable/embedded |
| ...

[Install-DevTools.ps1](attachments/986841103/Install-DevTools.ps1)
```

The attachment lives at `attachments/986841103/Install-DevTools.ps1` (54 KB). The wikilink `[[540934169 - Purchase Claude Code and Claude API Access]]` resolves cleanly to a sibling page in the corpus. Frontmatter validates the [`pipeline-spec.md` §4.4](pipeline-spec.md) schema.

## 3. Why this shape

Each design choice maps to a specific question Aaron asked, or to a real-world Confluence quirk we surfaced during the build.

| Decision | Rationale |
|---|---|
| **Atlassian Gateway URL** (`api.atlassian.com/ex/confluence/<cloud-id>/wiki/...`) | Surfaced empirically: Cloud API tokens return 401 against `su-jsm.atlassian.net/wiki/download/...` for attachments, but work cleanly through the gateway URL with a 302 → Media Services JWT redirect. Spec §4.1 also recommends gateway for [RFC-35](https://developer.atlassian.com/cloud/jira/platform/rfc-35-architectural-changes-affecting-custom-domains/) reasons. **Not optional — mandatory for attachment downloads to work at all.** |
| **Page-ID-prefixed filenames** | Solves four problems: same-title pages in different spaces don't collide; Confluence renames don't cascade wikilinks; the converter parses `page_id` from any filename; Obsidian resolves the exact-match wikilink form without alias gymnastics. (Spec §4.2.) |
| **Hierarchy preserved verbatim** | Confluence's parent-page chain becomes the folder path. We resolve both page-type and folder-type ancestors (the latter is a separate Confluence content type that earlier iterations silently dropped). |
| **Macro registry + ADF fallback-first** | Real SU pages mix legacy Confluence storage XML and modern ADF (Atlassian Document Format) — ~21% of ITSAI pages use ADF. The converter detects ADF, prefers `<ac:adf-fallback>` (storage-XML-shaped, reuses the macro registry), falls back to a JSON walker. Recursive walker + flat handler dict; adding a new macro = one entry. |
| **Attachment verifier** | Catches the false-green class: emitting `![[attachments/...]]` references when the file isn't on disk. Walker scans converted Markdown after each page, asserts every reference resolves to a file. Errors land as page warnings, not silent corruption. |
| **Per-page incremental state save** | A crash mid-pull preserves progress; pages already on disk skip on the next run via content_hash match. |
| **Dead-letter routing** | Conversion failures get full storage XML + traceback + warnings written to `conversion-failures/<space>/<page-id>.json`. The corpus stays clean; failures get reviewed before the next phase advances. |
| **IT-admin UI tone** | Dense information, monospace metadata, no consumer polish. The audience is IT staff running the tool, not students reading the output. |

## 4. How this answers Aaron's five questions

From the [project brief](README.md):

| # | Question | v1 status |
|---|---|---|
| **#1** | How should a KB article be formatted for ingestion? | **Answered in v1.** Canonical format = §4.4 frontmatter + Obsidian wikilinks + callouts + fenced code blocks + verified attachments. The spec describes it; the code enforces it; 34 ITSAI pages prove it on real content. |
| **#2** | What's the best way to create new KB articles, and in what hierarchy? | **Partial.** We preserve Confluence's hierarchy verbatim and we now reproduce folder-type ancestors correctly. The upstream question — "should hierarchy stay as-is or migrate to flat-with-tags?" — is open. Worth a separate memo once the wiki layer + query eval surface enough data to answer it empirically. |
| **#3** | Where should they live? | **Out of scope here** — Phase B addresses this. |
| **#4** | Who should have access? | **Out of scope here** — Phase B addresses this (with the OAuth 2.1 caveat from Julian's research). |
| **#5** | How do we keep them updated? | **Technical half answered.** Incremental sync, per-page content_hash skip, version-bump detection, tombstone behavior on Confluence deletes (spec §5). **Policy half open** — trustee model, retention windows, archival workflow are not v1's call; need ITS sign-off. |

## 5. raw vs. wiki — the SU caveat

Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (Apr 2026) describes the right pattern for the wiki layer: an LLM-maintained synthesis layer that compounds over time, with periodic lint, query-driven growth, and human curation. We adopt the structure with one essential modification for SU's context:

> **Confluence / `raw/` is the source of truth. The `wiki/` layer is an LLM-drafted, human-reviewed synthesis layer where every claim cites raw page IDs back to authoritative source.**

Unlike Karpathy's personal-notes use case where the LLM owns synthesis entirely, the SU instance has third-party authoritative content (Confluence pages owned by SU departments, not by the EDA team) and institutional liability if the wiki drifts. Mandatory citation + human-promotes-LLM-drafts is the discipline that keeps this safe.

The full operating rules live in [`wiki-operating-model.md`](wiki-operating-model.md) (shipped alongside this brief).

## 6. What v1 ships vs. what's deferred

**v1 ships** (as of 2026-05-13):

- Pull pipeline (ITSAI + any other Confluence space via config)
- Macro registry: 17 handlers + UnknownMacroHandler safety callout
- ADF fallback-first conversion
- Frontmatter (§4.4 schema, classifier fields emit `null`/`[]`)
- Attachment download + on-disk verification
- Folder-hierarchy preservation (pages + folder-type ancestors)
- Dead-letter routing
- Per-space sync state with incremental save
- Per-space pull lock (concurrent same-space pulls rejected)
- FastAPI service + SSE event streaming
- IT-admin UI
- 75 unit tests

**v1 explicitly defers** (with target versions):

| Component | Version | Why deferred |
|---|---|---|
| LLM-derived metadata classifier (Haiku 4.5 → audience / doc_type / tools / topics) | **v1.1** | Hook exists; budget validation tied to query-eval results (do we even need it?) |
| Sparse wiki layer | **v1.5** | Built per Karpathy pattern, seeded from corpus, validated by query eval |
| Chat-style query interface | **v1.5** | Eval vehicle + Aaron-demo surface; precursor to MCP |
| SQLite FTS5 index | **v2** | Files-first, indexer-second. Comes once chat-eval validates corpus quality |
| MCP server (Streamable HTTP, JWT/OAuth) | **v3** | Reuses `kb_ingest/` modules unchanged |
| Eval set as pytest job | **v3.1** | 30–50 queries with hit@3 + MRR@10; depends on MCP existing |
| Other Confluence spaces (Phase 2+) | **post-v3** | Architecture supports it today; gated by config |
| Wiki lint loop (Karpathy-style audit) | **post-v3** | Once wiki has >10 pages |

## 7. Open questions for the next 1:1

From [`pipeline-spec.md` §8](pipeline-spec.md), restated with v1 evidence:

1. **The "Answers" Confluence space** (the old Data Center site, no category in the inventory) — prior art on this KB problem, or defunct? Affects whether we de-duplicate or coexist.
2. **MCP rollout audience** — at what point does this go to broader SU users vs. stay internal to ITS/EDA? Defines OAuth-flow urgency.
3. **Attachment policy** — confirm v1's "preserve as raw refs" is fine for now. PDF/DOCX text extraction is a v1.5 milestone but needs Aaron's call on priority vs. classifier first.
4. **Sync infrastructure** — where does the sync job actually run? SU VM, Microsoft Fabric pipeline, Azure Function? Phase B planned SU VM; confirm or update.
5. **Filename scheme confirmation** — v1 uses page-ID prefix (`488210484 - Claude FAQ.md`) for collision/rename/lookup safety. Documented fallback if pushed back on aesthetics: human-readable filename + page-id in `aliases:`. Confirm or invoke fallback.
6. **Eval set authorship** — should real student/staff queries from existing Confluence search logs (if available) seed the 15-query eval? Beats synthetic queries.
7. **Classifier budget** — ~$5 one-time Haiku spend for the AI corpus is fine? Pre-approval for the 34-page pilot before any larger sweep.

## 8. What "next" looks like

Sequenced for the next ~2-3 weeks, in priority order:

1. **Wiki operating-model doc** ([`wiki-operating-model.md`](wiki-operating-model.md)) — the rules that make wiki/ promotion safe. (Drafted alongside this brief.)
2. **Simple chat interface** — `/api/query` endpoint + chat tab in the existing UI. Loads the 34 pages, sends them to Claude with the user's question, returns answer + cited page IDs. Both an eval vehicle and an Aaron-demo surface; not the production MCP, but the same Q→A→citation experience.
3. **Baseline eval** — 15 representative student/staff questions, asked through the chat interface in raw-only mode. Score answer quality + completeness; flag queries that needed cross-page synthesis (those are wiki-hub candidates).
4. **Karpathy-style proposal pass** — ask Claude to read all 34 raw pages and propose candidate wiki hubs (title, why it exists, raw pages synthesized, example queries answered). Output is a list, not pages yet.
5. **Seed 3 wiki hubs** — from the proposals, hand-curate the three obviously-cross-cutting ones (approved-tools, data-classification, mcp-and-connectors per spec §4.7). Every claim cites raw page IDs.
6. **Wiki eval** — same 15 questions, raw+wiki mode. Diff against baseline. Measurable improvement is the case for the wiki layer.
7. **Write-up + Aaron 1:1** — bring queries, baseline answers, wiki-improved answers, and the seven open questions above. Decision points: classifier budget greenlight, sync-infra target, eval-set ownership.

The exit criterion for this phase is "Aaron can see 15 real questions answered correctly, with citations, on his own corpus, in a UI that mirrors the eventual MCP experience." That's the demo. That's the v1.5 deliverable.

## 9. Why this work matters to the team

Aaron's project brief asked for "a process or pattern, not just a single answer." The v1 tool is that pattern: any SU Confluence space — ITHELP, Maxwell, the colleges, the schools — can be ingested with one config change. The hard work in v1 wasn't "convert this one space"; it was building the infrastructure that ingests *any* space without re-engineering. The macro registry, the ADF pipeline, the gateway-URL discovery, the attachment verifier, the dead-letter routing — all of that is space-agnostic.

The next phase (wiki layer + query surface) proves the second half of the project's purpose: *can an LLM actually answer questions from this corpus*. If the answer is yes, the path to a production MCP server is short — same modules, real auth, real transport. If no, the eval surfaces specific gaps Aaron's team can either fill in Confluence or close with targeted wiki hubs.

Either outcome is useful. Both are testable against the corpus we already have.
