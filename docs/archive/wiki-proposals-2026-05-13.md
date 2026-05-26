---
title: Wiki-Hub Proposals — Step 4 Karpathy Pass
status: draft (LLM-generated; needs human curation before Step 5)
date: 2026-05-13
project: kb-ingestion-internship
phase: Step 4 of next-phase-plan.md
model: claude-opus-4-7
corpus: 29 ITSAI pages (test fixtures excluded)
baseline_context: eval-baseline-2026-05-13.md (14 ✅ / 1 ⚠️ / 0 ❌)
prompt: see prototypes/confluence-to-md-v2/scripts/run_proposals.py
cost_usd: 1.1498
latency_s: 26.5
---

# Wiki-Hub Proposals — Step 4

Proposal pass from claude-opus-4-7 over the full 29-page raw corpus. The model was given
the v1.5 baseline context (raw-only is already strong; wiki's job is canonical
synthesis and citation depth, not rescue) and the wiki-operating-model rules.

Step 5 picks 1-3 of these to actually build as `output/wiki/*.md` hubs. The model's
top-pick recommendation appears in the meta-commentary at the bottom.

---

```yaml
candidates:
  - title: "Approved AI Tools at SU: Data Policy & Capability Comparison"
    why_it_exists: "No single page compares the approved tools side-by-side on data handling (retention, training, ownership, allowed data classifications) — the master list [[488144948]] is just links, and each FAQ ([[488210484]], [[522289260]], [[498597967]]) only covers one tool in isolation."
    addresses_eval_queries: ["q03", "q04"]
    synthesizes:
      - "488144948"
      - "488210484"
      - "522289260"
      - "498597967"
      - "483525103"
      - "544538648"
      - "534642749"
      - "544505857"
    example_queries:
      - "Which approved AI tools can I use with FERPA or other Confidential university data?"
      - "How long does Claude vs Copilot vs Gemini retain my chats, and do any of them train on my data?"
      - "Who owns the outputs I generate in Claude, Copilot, or Gemini?"
    draft_sketch: |
      Opens with the canonical list of approved tools and the universal rule (logged in with NetID = all
      data classifications permitted, governed by the IT Acceptable Use policy). Core of the hub is a
      comparison matrix across Claude, Copilot, Gemini, mentorAI: data ownership, training on user data,
      retention period, incognito/temporary mode, admin/IT access posture. Closes with a "which tool for
      which job" pointer to the creative-workflows page.
    leverage: "high"
    leverage_rationale: "Directly fixes the one baseline-⚠️ query (q03) by giving citation-rich per-tool depth in a single canonical page, and stabilizes q04 which currently relies on the model finding adjacent FAQs."

  - title: "Claude at SU: Product Surface Map (Chat, Code, API, Cowork, Connectors, MCP)"
    why_it_exists: "Claude at SU spans many distinct surfaces — Chat, Code, API, Cowork, M365 connector, custom connector requests, local MCP, Filesystem — and no single page maps which surface is enabled, which costs money, which is disabled, and how they relate."
    addresses_eval_queries: ["q11"]
    synthesizes:
      - "534642749"
      - "522158118"
      - "540934169"
      - "836698117"
      - "544210961"
      - "841875458"
      - "837517313"
      - "988774401"
      - "986841103"
    example_queries:
      - "What's the difference between Claude Chat, Claude Code, Cowork, and MCP — and which can I actually use at SU?"
      - "How do I connect Claude to SharePoint, Power BI, or another tool?"
      - "Why is Claude Cowork disabled and what should I use instead?"
    draft_sketch: |
      Opens with a "what's enabled / what costs extra / what's disabled" status table covering every
      Claude surface at SU. Middle section groups surfaces by purpose: conversational (Chat), agentic
      (Code, Cowork-disabled), integrations (M365 connector enabled, Atlassian enabled, custom via
      request, local MCP, Filesystem). Each row links to its raw page. Closes with decision guidance:
      "I want to connect Claude to X — which path do I take?"
    leverage: "high"
    leverage_rationale: "Stabilizes q11 (MCP) which today works only because the model finds adjacent pages, and creates a canonical entry point for the rapidly-growing Claude-ecosystem questions that currently span 8+ raw pages."

rejected_candidates:
  - title: "Creative AI Workflows Hub"
    why_rejected: "Page [[515670055]] already owns this view as a strong synthesis page; a hub would be a 1:1 rewrite."

  - title: "mentorAI Complete Guide"
    why_rejected: "[[544505857]] is already the index, and [[567279621]] is an exhaustive settings reference. A hub would duplicate already-strong raw pages without adding a cross-cutting view."

  - title: "Claude Use Cases for Students (Study, Career, Email, Research)"
    why_rejected: "The individual pages ([[511279124]], [[511246346]], [[516325410]], [[572194844]], [[500236296]]) are already discoverable from [[534642749]]; baseline likely answers these well and a hub adds little beyond a link list."

  - title: "AI for Meeting & Document Workflows"
    why_rejected: "Interesting cross-tool view (Copilot transcription → Claude summarization → NotebookLM audio) but [[515670055]] already covers this creatively, and no eval query targets it."

  - title: "Data Privacy & Governance Across SU AI Tools"
    why_rejected: "Substantially overlaps with the Approved Tools comparison hub above; folding privacy into that hub is sharper than splitting it out."

  - title: "Getting Started with AI at SU"
    why_rejected: "[[483525103]] is already the landing/hub page for this; a new hub would be a 1:1 duplicate."
```

**Meta-commentary:** Build the **Approved AI Tools Comparison** hub first — it is the only candidate that directly converts a baseline-⚠️ query (q03) into a ✅ and addresses a real, recurring SU compliance question that no single raw page can answer well. Build the **Claude Product Surface Map** second; it stabilizes q11 and absorbs the largest cluster of raw pages (9), where today's correct answers depend on lucky adjacent-page retrieval. Everything else in the corpus is either already well-owned by a single strong raw page or is creative/tutorial content that doesn't need a synthesis layer yet.

---

## Run metadata

- Model: `claude-opus-4-7`
- Cost: **$1.1498** (input=68, output=1952, cache_write=53461, cache_read=0)
- Latency: 26.5s
- Reproducer: `python scripts/run_proposals.py --model claude-opus-4-7`
