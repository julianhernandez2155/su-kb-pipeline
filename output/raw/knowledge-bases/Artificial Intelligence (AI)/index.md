# Space Index — Artificial Intelligence (AI)

Confluence space `ITSAI` mirrored as 29 reviewed pages. Covers every AI tool Syracuse University supports, the data-handling policy that governs them, how to access them, MCP/connectors, and example use cases.

## How to route a question to this space

| If the question is about… | Start here |
|---|---|
| Which AI tools are approved for university data, data classification policy | Wiki hub: `wiki/approved-ai-tools-for-university-data.md` |
| What's enabled/disabled at SU across Claude's surfaces (Chat, Code, Cowork, connectors, MCP) | Wiki hub: `wiki/claude-at-syracuse-product-surface-map.md` |
| A specific Claude policy detail (retention, training, traveling abroad, etc.) | `AI @ Syracuse University/AI/Claude/488210484 - Claude - Frequently Asked Questions.md` |
| Installing or configuring Claude Code | `AI @ Syracuse University/AI/Claude/986841103 - Claude Code Setup.md` |
| Microsoft Copilot policy | `AI @ Syracuse University/AI/Copilot/522289260 - Copilot – Frequently Asked Questions.md` |
| Google Gemini or NotebookLM | `AI @ Syracuse University/AI/Gemini/` |
| mentorAI / Clementine | `AI @ Syracuse University/AI/Clementine Platform/` |
| Example student/staff use cases for Claude | `AI @ Syracuse University/AI/Claude/Example Uses/` |
| The space-wide landing page (orientation, signup links) | `483525103 - AI @ Syracuse University.md` |

## Subcategory map

### `AI @ Syracuse University/AI/Claude/` — 10 pages

The largest subtree. Covers Claude policy, access, products, connectors, and MCP.

- **`488210484 - Claude FAQ`** — the canonical policy page. Data classification, retention (2 years), training opt-out, travel restrictions, IT staff access, premium-seat pricing ($2,400/yr).
- **`534642749 - Claude Enterprise at Syracuse University`** — overview, who can access, getclaude.syr.edu signup.
- **`522158118 - Understanding Claude Products`** — Chat vs. Code vs. API distinction.
- **`540934169 - Purchase Claude Code and Claude API Access`** — request workflow + pricing.
- **`986841103 - Claude Code Setup`** — Windows install via `Install-DevTools.ps1`.
- **`544210961 - Connect Claude to M365`** — M365 connector setup (enabled SU-wide).
- **`836698117 - Claude Cowork`** — disabled SU-wide; security rationale.
- **`837517313 - Claude Local MCP - Connecting Claude Desktop to Power BI`** — local MCP example.
- **`841875458 - Requesting a Claude Connector`** — connector request process, SOC 2 requirement.
- **`988774401 - Working with SharePoint Files in Claude`** — Filesystem connector + OneDrive shortcut pattern.

### `AI @ Syracuse University/AI/Claude/Example Uses/` — 5 pages

Concrete student/staff workflows.

- **`500236296`** — Meeting Summaries
- **`511246346`** — Career Project (resumes, cover letters, interview prep)
- **`511279124`** — Study Project (uploading slides/PDFs, quizzes, flashcards)
- **`516325410`** — Drafting Emails
- **`572194844`** — AI Research Assistant (literature review, multi-document analysis)

### `AI @ Syracuse University/AI/Clementine Platform/` — 6 pages

SU's private AI platform (mentorAI) for course-specific AI assistants.

- **`544505857 - mentorAI @ Syracuse University`** — overview, what it is, who it's for.
- **`535068673 - mentorAI Creating A Mentor`** — how to build a new mentor.
- **`567279621 - mentorAI Settings & Options`** — LLM selection (Claude/ChatGPT/Gemini), datasets, safety, memory.
- **`700121089 - mentorAI - Tools`** — image generation, code interpreter, screen sharing, web search.
- **`591101962 - mentorAI - Using the API`** — programmatic access.
- **`895451142 - Clementine Class Search`** — semester catalog search built on Clementine.

### `AI @ Syracuse University/AI/Copilot/` — 1 page

- **`522289260 - Copilot FAQ`** — Microsoft Copilot policy (retention, training, M365 integration).

### `AI @ Syracuse University/AI/Gemini/` — 4 pages

- **`498597967 - Google Gemini FAQ`** — policy: training, retention, drive access.
- **`544538648 - Google Gemini at Syracuse University`** — overview, NetID@g.syr.edu login.
- **`515801118 - Smart Study Companion with Gemini`** — flashcards, quizzes, study guides workflow.
- **`530546723 - How to use Google NotebookLM`** — Studio features (audio overviews, mind maps), source limits.

### `AI @ Syracuse University/AI/AI - General Information/` — 2 pages

- **`488144948 - Approved Tools for Use with University Data`** — the master list. The canonical answer to "what AI tools can I use with X data?"
- **`515670055 - Creative AI Workflows & Tools`** — practical decision guide across Claude/Copilot/Gemini.

### Top-level page

- **`483525103 - AI @ Syracuse University`** — the landing page for the whole space. Lists each tool with model name, access URL, brief description. Good first read if you don't know where to start.

## Wiki hubs that draw from this space

| Hub | Synthesizes | When to prefer the hub over individual pages |
|---|---|---|
| `wiki/approved-ai-tools-for-university-data.md` | 8 pages (Approved Tools list + per-tool FAQs + per-tool overviews) | Cross-platform policy comparisons. Side-by-side retention/training/ownership. Compliance-flavored questions. |
| `wiki/claude-at-syracuse-product-surface-map.md` | 10 pages (every Claude surface) | "What's enabled vs disabled at SU." "How do I connect Claude to X." "Why is Cowork off." Demo-worthy structure. |

## Notes

- Test fixtures (`(Test) Resume Tailor Machine Brain/` and `Summer Intern 2026/`) are present on disk but excluded by `sukb.chat.query.load_raw_corpus` from the queryable corpus. They're not counted in the 29.
- Page IDs in this space are stable across the Cloud (`su-jsm.atlassian.net`) and Data Center (`answers.atlassian.syr.edu`) Atlassian sites — see `learnings/confluence_at_syracuse.md` in the SU_AI_Intern workspace.
