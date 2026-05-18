---
title: "Approved AI Tools at Syracuse: Data Policy & Capability Comparison"
type: hub
status: reviewed
synthesizes:
  - "488144948"
  - "488210484"
  - "522289260"
  - "498597967"
  - "483525103"
  - "544538648"
  - "534642749"
  - "544505857"
created: 2026-05-14
updated: 2026-05-14
reviewer: jlhernan@syr.edu
review_notes: "v2 — Codex cleanup pass softened the universal NetID claim to scope it explicitly to Claude and Copilot."
tags:
  - hub
  - ai-policy
  - approved-tools
  - data-classification
---

# Approved AI Tools at Syracuse: Data Policy & Capability Comparison

This hub consolidates data-handling policy and access information for the AI tools Syracuse University has approved for use with university data. The per-tool FAQ pages each cover a single platform; this page brings them together so you can compare retention, training, ownership, and allowed data classifications side by side.

## The Approved Tools List

Syracuse University supports the following tools for use with university data when the user is logged in with Syracuse University credentials (NetID) [[488144948]]:

- Anthropic Claude Enterprise (request access at getclaude.syr.edu) [[488144948]]
- mentorAI for Syracuse University [[488144948]]
- Microsoft Copilot Work or Web [[488144948]]
- Google Gemini (login with NetID@g.syr.edu) [[488144948]]
- Blackboard's AI [[488144948]]
- OpenAI ChatGPT Teams (request access via IT Support) [[488144948]]
- Adobe Firefly [[488144948]]
- Gradescope [[488144948]]

The four most prominently featured general-purpose assistants on the AI hub are Claude Enterprise, the Clementine Platform / mentorAI, Microsoft Copilot, and Google Gemini [[483525103]].

## The NetID Rule (Claude and Copilot)

Claude and Copilot each explicitly state that all Data Classification Definitions of university data may be used when the user is logged in with university credentials (NetID) [[488210484]][[522289260]]. Microsoft Copilot specifically permits use "with all Data Classification Definitions of university data that align with Syracuse's data handling policies" when logged in with SU credentials [[522289260]].

The approved-tools list at [[488144948]] enumerates the broader set of tools approved for university data, but not every tool on that list has an equally detailed data-classification FAQ — see the per-tool sections below for what the corpus says about each.

For Google Gemini, access requires signing in with the SU Google account (`NetID@g.syr.edu`) rather than a personal Gmail [[498597967]][[544538648]].

Users are still cautioned to be careful about data uploaded to shared artifacts — for example, items shared from a Claude Project or Claude Artifact [[488210484]].

## Side-by-Side Comparison

| Policy Dimension | Claude Enterprise | Microsoft Copilot | Google Gemini | mentorAI |
| --- | --- | --- | --- | --- |
| **Output / input ownership** | User retains ownership of inputs; granted ownership of outputs Claude creates [[488210484]] | User retains ownership of inputs; granted ownership of outputs Copilot creates [[522289260]] | User retains full control and ownership; data is treated as customer data [[498597967]] | Not specified in corpus |
| **Trains on user data by default?** | No — uploaded data and chats are not used to train Claude models by default. Exception: explicitly submitted feedback or bug reports may be used for training [[488210484]] | No — Microsoft does not use content, prompts, or Copilot interactions from SU accounts to train its AI models [[522289260]] | No — prompts, chats, and uploaded content in Gemini for Education are not used to train Google's generative AI models [[498597967]][[544538648]] | Not specified in corpus |
| **Retention period** | All data retained for 2 years; deleted items are no longer visible but remain in the platform for the retention period [[488210484]] | Conversations stored in user's M365 mailbox in a hidden folder; recoverable/searchable by admins for up to 30 days after user deletion, unless mailbox has different retention policies [[522289260]] | Not specified in corpus | Not specified in corpus |
| **Private / temporary chat mode** | Incognito chats are not saved to chat history or to Claude memory, but still retained on the platform per the standard retention policy [[488210484]] | Temporary Chat — not saved to chat history; conversation no longer visible after window is closed/refreshed, but still subject to M365 retention policies [[522289260]] | Not specified in corpus | Not specified in corpus |
| **Human review by vendor?** | Not specified in corpus | Not specified in corpus | Chats are not human-reviewed or accessed by Google personnel to improve AI models [[498597967]] | Not specified in corpus |
| **SU IT staff access posture** | Data is "inherently accessible to authorized IT staff" for support/security/maintenance; governed by IT Resources Acceptable Use policy and Information Security Framework [[488210484]] | Same posture — data within SU's M365 environment may be accessed by authorized IT staff for support/maintenance/security/backup; governed by IT Resources Acceptable Use policy and Information Security Framework [[522289260]] | Same posture — access is governed by the IT Resources Acceptable Use policy and Information Security Framework [[498597967]] | Not specified in corpus |
| **Drive / mailbox auto-access?** | Not specified in this hub's source pages (see the Product Surface Map hub for connector behavior) | Not specified in corpus | Gemini does not have unrestricted access to your entire Google Drive — only files you explicitly open, reference, or share in a session [[498597967]] | Not specified in corpus |

## Tool-Specific Caveats

### Claude Enterprise

- The 2-year retention applies to all chats and projects, and deleted items continue to be retained on the platform independent of user visibility [[488210484]].
- Personalization features (memory across past chats and projects) are user-configurable in Claude Settings [[488210484]].
- Anthropic restricts access from certain countries; attempting to access from a prohibited country may result in an account ban [[488210484]].
- When Claude executes code through its computer tools (bash, Python, R), network access is disabled to prevent code from transmitting university data to external endpoints [[488210484]].

### Microsoft Copilot

- Copilot conversation data is ultimately stored in the user's M365 mailbox; standard mailbox retention policies can override the 30-day default recoverability window [[522289260]].
- Copilot offers personalization and memory settings configurable by users and administrators [[522289260]].
- The Copilot buttons that appear in Word, Excel, Teams, etc. are shortcuts to the same Copilot experience built into each app — they do not extend across or pull from data in other apps [[522289260]].

### Google Gemini

- Use is covered by the Google Workspace for Education Terms of Service, which Google describes as "enterprise-grade data protection" [[498597967]].
- The corpus does not specify a retention period for Gemini chats.

### mentorAI

- mentorAI is described as Syracuse University's private AI platform for Teaching & Learning and AI Innovation, available to all SU students, faculty, and staff [[483525103]][[544505857]].
- The corpus does not contain a published data-retention, training, or ownership FAQ for mentorAI comparable to Claude's, Copilot's, or Gemini's.

## Which Tool for Which Job

The AI hub and the Claude Enterprise overview position these tools for the same core use cases — writing assistance, research, problem solving, learning, data analysis, and creative collaboration [[534642749]][[544538648]]. Differentiation in the corpus is primarily around platform integration and access model:

- **Microsoft Copilot** is built into the Microsoft 365 surface (Word, Excel, PowerPoint, Teams, Outlook, OneNote) and uses OpenAI's GPT-5 model [[483525103]].
- **Google Gemini** at SU uses Google's 2.5 Pro model and includes guided learning, image generation, and a canvas editor [[483525103]].
- **Claude Enterprise** is positioned as a general-purpose "intelligent digital colleague" with no coding/technical knowledge required to use [[534642749]].
- **mentorAI (Clementine Platform)** is the SU-run platform for AI-powered personalized assistants for teaching, learning, and innovation [[483525103]][[544505857]].

## Access URLs

| Tool | Access URL |
| --- | --- |
| Claude Enterprise | getclaude.syr.edu [[483525103]][[488144948]] |
| mentorAI / Clementine Platform | mentor.ai.syr.edu [[483525103]][[544505857]] |
| Microsoft Copilot | m365.cloud.microsoft/chat [[483525103]] |
| Google Gemini | gemini.google.com/app (login as NetID@g.syr.edu) [[483525103]][[488144948]] |

## Sources

- [[488144948 - Approved Tools for Use with University Data]]
- [[488210484 - Claude - Frequently Asked Questions]]
- [[522289260 - Copilot – Frequently Asked Questions]]
- [[498597967 - Google Gemini - Frequently Asked Questions]]
- [[483525103 - AI @ Syracuse University]]
- [[544538648 - Google Gemini at Syracuse University]]
- [[534642749 - Claude Enterprise at Syracuse University]]
- [[544505857 - mentorAI @ Syracuse University]]