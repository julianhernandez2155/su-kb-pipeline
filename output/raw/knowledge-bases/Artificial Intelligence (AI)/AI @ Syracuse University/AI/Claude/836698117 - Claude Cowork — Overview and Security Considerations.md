---
page_id: '836698117'
title: Claude Cowork — Overview and Security Considerations
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/836698117/Claude+Cowork+—+Overview+and+Security+Considerations
visibility_signal: accessible_to_sync_user
restriction_check: not_checked
restricted_to: []
space_key: ITSAI
space_name: Artificial Intelligence (AI)
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path:
- AI @ Syracuse University
- AI
- Claude
last_modified: '2026-02-20T16:24:40.916Z'
version: 2
contributors:
- 712020:882951bc-9249-4b41-8242-4d19030b3116
contributors_count: 1
content_hash: sha256:220b802066500fd1cd414cae60f439be8ce8e18153227518afd01cf9b79b5256
synced_at: '2026-05-19T15:04:17Z'
last_sync_status: ok
labels: []
tags_original: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 87
maintenance_signal: fresh
word_count: 927
char_count: 6251
token_estimate: 1786
attachment_count: 0
conversion_warnings: []
---

---

### What is Claude Cowork?

Claude Cowork is a feature built into the Claude Desktop application that gives Claude the ability to act as an autonomous desktop agent. Rather than responding to prompts one message at a time like standard Claude Chat, Cowork can take on complex, multi-step tasks and execute them on your behalf  reading, editing, creating, and organizing files directly on your computer.

You point Cowork at a folder on your machine, describe the outcome you want, and Claude makes a plan and works through it step by step. Example use cases include assembling an expense report from a folder of receipt photos, reorganizing a messy downloads folder, drafting documents from source materials, or converting files between formats.

Cowork is built on the same agentic architecture that powers Claude Code, but packaged in a more approachable interface for non-coding tasks. It launched in January 2026 as a research preview and is available on both macOS and Windows through the Claude Desktop app.

---

### How Does Cowork Differ from Claude Chat?

In standard Claude Chat (what most Syracuse University users access at [claude.ai](http://claude.ai)), Claude responds to your messages conversationally. You upload files, ask questions, and get answers  but Claude does not directly access or modify anything on your computer.

Cowork is fundamentally different. When you grant Cowork access to a folder, Claude can autonomously read, write, create, and permanently delete files within that folder. It can also execute code, use browser extensions (Claude in Chrome), and connect to external services through plugins and MCP connectors. It operates more like a digital coworker than a chatbot.

---

### Current Status at Syracuse University

**Cowork is currently disabled for all users in the Syracuse University Claude Enterprise organization.**

We made this decision deliberately after evaluating the feature's security posture and its fit within our enterprise compliance requirements. While Cowork offers compelling productivity potential, several significant concerns need to be addressed before we can responsibly enable it for the campus community.

---

### Why Cowork Is Not Yet Enabled

#### 1. No Audit Log or Compliance API Coverage

This is the most critical concern. Anthropic has explicitly stated that Cowork activity is **not captured in Audit Logs, the Compliance API, or Data Exports**. Conversation history is stored locally on the user's computer only.

For Syracuse University, this means we would have no centralized visibility into what Cowork is being used for, what files it accesses, or what actions it takes. This creates a significant gap in our ability to meet institutional compliance requirements, respond to incident investigations, or monitor for misuse. Anthropic's own documentation states: If your organization requires audit trails for compliance purposes, do not enable Cowork for regulated workloads.

#### 2. Data Stored Locally, Not Subject to Enterprise Retention

Cowork stores all conversation history locally on the user's machine. This data is not subject to Anthropic's standard data retention timeframe or our enterprise data governance policies. This means Cowork session data could persist indefinitely on a user's laptop (or be lost entirely if the machine is reimaged), with no organizational control over retention or deletion.

#### 3. Local File System Access Creates Data Exposure Risk

Cowork can read, write, and permanently delete files in any folder a user grants it access to. If a user inadvertently points Cowork at a folder containing sensitive university data  student records, financial documents, credentials, research data  that data could be processed by Cowork with no audit trail and no organizational visibility. The risk is amplified because users may not fully understand the scope of access they are granting.

#### 4. Prompt Injection and Agentic Risk

Because Cowork operates autonomously (reading files, browsing the web, executing code), it is susceptible to prompt injection attacks  where malicious content hidden in a file or website attempts to alter Claude's behavior. Anthropic acknowledges this risk directly, noting that agent safety is still an active area of development. There have been documented real-world incidents, including cases where Cowork accidentally deleted files a user did not intend to be removed.

#### 5. No Granular Admin Controls

During the research preview, Cowork is controlled by a single organization-wide toggle  on or off for everyone. There is no ability to enable Cowork for specific users, roles, or departments. Similarly, plugins installed within Cowork are saved locally to each user's machine and cannot be centrally provisioned or managed by admins. This all-or-nothing approach does not align with our need for role-based access and centralized policy management.

#### 6. Research Preview Status

Anthropic classifies Cowork as a research preview  meaning the feature is still in active development, safety mechanisms are still being hardened, and the product may change significantly. Enabling a research preview feature across an enterprise organization of Syracuse's scale carries inherent risk, particularly given the other concerns listed above.

---

### What Can I Use Instead?

Syracuse University users have access to a robust set of Claude capabilities that do not carry the same security concerns:

- **Claude Chat** ([claude.ai](http://claude.ai))  Full conversational AI with file upload, artifacts, projects, web search, and connectors. Covered by enterprise audit logs and compliance controls.
- **Claude Code**  Terminal-based agentic coding tool for developers. Available via premium seat purchase. Covered by enterprise audit infrastructure.
- **Claude API**  Programmatic access for building applications and automations. Available via premium seat purchase.

For more information on these products, see [[522158118 - Understanding Claude Products_ Chat, Code, and API]].

---

### Questions?

If you have questions about Cowork or other Claude features, please reach out:

- **ITS Help Desk**: 315-443-2677  [help@syr.edu](mailto:help@syr.edu)

*Page last updated: February 2026*
