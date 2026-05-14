---
title: "Claude at Syracuse: Product Surface Map"
type: hub
status: reviewed
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
  - "488210484"
created: 2026-05-14
updated: 2026-05-14
reviewer: jlhernan@syr.edu
review_notes: "v2 — Codex cleanup pass: added 488210484 to synthesizes for the $2,400/year citation; softened the local-MCP framing to clarify context is still seen by the model."
tags:
  - hub
  - claude
  - product-map
  - mcp
  - connectors
---

# Claude at Syracuse: Product Surface Map

Claude at Syracuse University is not a single product. It spans conversational interfaces, agentic coding tools, programmatic APIs, and a growing set of connectors and integrations — some enabled by default, some requiring a paid premium seat, some disabled by ITS policy. This hub maps every Claude surface, what status it has at SU, and how to choose among them.

## Status at a Glance

| Surface | Status at SU | Cost | Primary Use |
|---|---|---|---|
| Claude Chat | Enabled for all SU users [[534642749]] | Included in Enterprise license [[534642749]] | Conversational AI, writing, analysis, artifacts, projects [[522158118]] |
| Claude Code | Available via request | Premium seat (departmental) or pay-as-you-go credits [[540934169]] | Terminal-based agentic coding [[522158118]] |
| Claude API | Available via request | Same as Claude Code — premium seat or credits [[540934169]] | Programmatic integration into applications [[522158118]] |
| Claude Cowork | Disabled organization-wide [[836698117]] | n/a | (Would be) autonomous desktop agent [[836698117]] |
| Microsoft 365 connector | Enabled for all SU users [[544210961]] | Included | Access SharePoint, OneDrive, Teams, Outlook from Claude [[544210961]] |
| Atlassian connector | Enabled for all SU users [[841875458]] | Included | Access Jira tickets and Confluence pages [[841875458]] |
| Other enterprise connectors | Request-based, ITS review required [[841875458]] | Varies | Third-party tool integration via MCP [[841875458]] |
| Local MCP (Claude Desktop) | User-configurable | n/a | Connect Claude Desktop to local apps like Power BI [[837517313]] |
| Filesystem connector (Claude Desktop) | User-configurable [[988774401]] | n/a | Read, edit, and create local files including SharePoint shortcuts [[988774401]] |

## Conversational Surface: Claude Chat

Claude Chat is the default surface that any SU community member can access at claude.ai after signing up at getclaude.syr.edu [[534642749]]. It's a conversational interface available via web, mobile, and desktop apps [[522158118]].

Chat is intended for everyday tasks: writing assistance, analysis, brainstorming, coding help, research, and creating Artifacts or Projects [[522158118]]. It is covered by SU's Enterprise agreement with Anthropic, which protects uploaded data from being used to train Anthropic's models by default [[534642749]].

## Agentic Surfaces

Claude offers two agentic surfaces with very different statuses at SU.

### Claude Code — Available with Premium Seat

Claude Code is a command-line tool that brings Claude into your terminal for agentic coding workflows, working directly within your local development environment [[522158118]]. The Claude Enterprise license does **not** include Claude Code — access requires either a Premium seat or pay-as-you-go credits [[540934169]].

Faculty and staff can request a Premium seat through the Claude Premium Access Package, with departmental funding on a pro-rated/contract basis [[540934169]] — the Claude FAQ documents the current rate as $2,400/year per seat [[488210484]]. Alternatively, departments can authorize pay-as-you-go credit purchases up to $200/month via the Claude Code API Interest and Access Request Form [[540934169]]. Students must purchase credits with personal funds via the Anthropic Console, though their usage remains protected under SU's Enterprise agreement [[540934169]].

Setup on Windows is documented and includes an automated PowerShell script (`Install-DevTools.ps1`) that installs Node.js, Git Portable, Python, VS Code, and Claude Code itself [[986841103]]. Configuration requires signing in with `netid@syr.edu` and selecting the Syracuse University organization [[986841103]].

### Claude Cowork — Disabled

Cowork is built into Claude Desktop and gives Claude the ability to act as an autonomous desktop agent — reading, editing, creating, and organizing files on your computer [[836698117]]. It launched as a research preview in January 2026 [[836698117]].

**Cowork is currently disabled for all users in SU's Claude Enterprise organization** [[836698117]]. ITS cited several concerns:

- Cowork activity is **not** captured in Audit Logs, the Compliance API, or Data Exports — conversation history is stored locally only [[836698117]].
- Local file system access creates data exposure risk for sensitive university data [[836698117]].
- Cowork is susceptible to prompt injection attacks given its autonomous nature [[836698117]].
- There are no granular admin controls — it's an org-wide on/off toggle [[836698117]].
- It remains a research preview and may change significantly [[836698117]].

Users who want similar local-file capabilities should look at the **Filesystem connector** on Claude Desktop instead (see below) [[836698117]].

## Integration Surfaces

Claude integrates with external systems via the Model Context Protocol (MCP) [[841875458]]. SU offers three distinct integration paths.

### Pre-Enabled Enterprise Connectors

**Microsoft 365** is enabled for all SU users [[544210961]]. Once connected, Claude can access Microsoft Teams messages, Outlook emails, and SharePoint and OneDrive documents [[544210961]]. Activation is done per-user under Claude Settings → Connectors → Microsoft 365 → Connect, signing in with `netid@syr.edu` [[544210961]].

**Atlassian** is also enabled, allowing Claude to read Jira tickets and Confluence pages [[841875458]].

### Requesting a New Enterprise Connector

If a third-party tool offers a Claude connector you'd like enabled organization-wide, submit a request to aihelp@syr.edu including the connector documentation, business use case, vendor contract status, and a SOC 2 Type II report from the vendor [[841875458]].

ITS reviews requests against several criteria: vendor SOC 2 Type II availability (the most important requirement), existing SU contract, data classification risk, breadth of campus benefit, and vendor maturity [[841875458]]. Requests are unlikely to be approved without a SOC 2 report, without an existing SU contract, or if the connector would expose restricted data without adequate controls [[841875458]].

### Local MCP (Claude Desktop)

Local MCP is an open-source standard from Anthropic that allows the Claude Desktop app to securely connect to data and tools running on your local computer — files, folders, databases, and APIs — without requiring enterprise admin approval [[837517313]]. The corpus describes local MCP connections as running on the user's machine and not requiring enterprise connector approval [[841875458]]; users should still follow SU data-handling rules for any content they expose to Claude, since context surfaced through MCP is still seen by the model.

A documented example is the **Power BI Modeling MCP**, which is installed via a VS Code extension, then registered in Claude Desktop's config file under `mcpServers` [[837517313]]. Once configured, Claude Desktop can connect to an open Power BI report and assist with modeling tasks [[837517313]].

### Filesystem Connector

The Filesystem connector — available in Claude Desktop — lets Claude read, find, edit, and create files in directories you explicitly grant access to [[988774401]]. It cannot delete files, cannot search across SharePoint sites you haven't granted access to, and does not provide Outlook/calendar/Teams access [[988774401]].

A common pattern is to combine Filesystem with a SharePoint shortcut in OneDrive: add the SharePoint folder via "Add shortcut to My files," then point the Filesystem connector at your `OneDrive - Syracuse University` path [[988774401]]. This effectively lets Claude work with SharePoint files even though it isn't searching SharePoint directly [[988774401]].

## Decision Guidance: "I want to connect Claude to X"

| Goal | Recommended path |
|---|---|
| Chat with Claude about university documents | Use Claude Chat with file uploads or the M365 connector [[544210961]] |
| Have Claude work on local files (including SharePoint via shortcut) | Install Claude Desktop, enable the Filesystem connector [[988774401]] |
| Have Claude do autonomous multi-step desktop work | Not available at SU — Cowork is disabled [[836698117]]; use Claude Chat or Claude Code instead [[836698117]] |
| Write or refactor code from the terminal | Request Claude Code via Premium seat or credits [[540934169]] |
| Build an application that calls Claude programmatically | Request Claude API access (packaged with Claude Code) [[540934169]] [[522158118]] |
| Integrate Claude with Jira or Confluence | Already enabled — use the Atlassian connector [[841875458]] |
| Integrate Claude with another third-party SaaS tool | Submit a connector request to aihelp@syr.edu with SOC 2 Type II report [[841875458]] |
| Connect Claude Desktop to a local app like Power BI | Configure a local MCP server in Claude Desktop's config [[837517313]] |

## What's Covered Where

- **Audit logs and enterprise compliance:** Claude Chat, Claude Code, and Claude API are covered by enterprise audit infrastructure [[836698117]]. Cowork is not [[836698117]].
- **Data protection under SU's Enterprise agreement:** Applies to Claude Chat usage signed in with SU credentials, and also extends to credit-based Claude Code/API usage when purchased through the SU Enterprise account [[540934169]].
- **Unused credits at separation:** Lost when a user leaves the university; both faculty/staff and student guidance pages note this [[540934169]].

## Sources

- [[534642749 - Claude Enterprise at Syracuse University]]
- [[522158118 - Understanding Claude Products: Chat, Code, and API]]
- [[540934169 - Purchase Claude Code and Claude API Access]]
- [[836698117 - Claude Cowork — Overview and Security Considerations]]
- [[544210961 - Connect Claude to M365]]
- [[841875458 - Requesting a Claude Connector]]
- [[837517313 - Claude Local MCP - Connecting Claude Desktop to Power BI]]
- [[988774401 - Working with SharePoint Files in Claude]]
- [[986841103 - Claude Code Setup]]