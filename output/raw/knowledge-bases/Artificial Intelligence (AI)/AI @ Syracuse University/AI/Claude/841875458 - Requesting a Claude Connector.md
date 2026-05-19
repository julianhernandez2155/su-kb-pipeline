---
page_id: '841875458'
title: Requesting a Claude Connector
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/841875458/Requesting+a+Claude+Connector
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
last_modified: '2026-02-23T17:49:01.170Z'
version: 2
contributors:
- 712020:882951bc-9249-4b41-8242-4d19030b3116
contributors_count: 1
content_hash: sha256:d7e9041ecf8ce2e35ae52c69f9ac0ff66da998a367aa0ab1475da476feb23a7b
synced_at: '2026-05-19T15:04:23Z'
last_sync_status: ok
labels: []
tags_original: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 84
maintenance_signal: fresh
word_count: 676
char_count: 4356
token_estimate: 1245
attachment_count: 0
conversion_warnings: []
---

Claude Enterprise supports connectors  integrations that allow Claude to read from and interact with third-party tools and services you use at work. Some connectors (like Microsoft 365 and Atlassian) are already enabled for all SU users. Others require a review and approval before ITS can enable them university-wide.

## What Is a Claude Connector?

Connectors extend Claude's capabilities by giving it access to external systems via the Model Context Protocol (MCP). For example, the Microsoft 365 connector lets Claude search your SharePoint files and Teams content. The Atlassian connector allows Claude to read Jira tickets and Confluence pages.

Connectors are configured at the organization level by ITS administrators. Once enabled, individual users can connect their personal accounts and toggle connectors on or off within their Claude settings.

## How to Request a New Connector

If a tool you use has a Claude connector and you would like ITS to enable it, submit a request to [aihelp@syr.edu](mailto:aihelp@syr.edu) with the following:

1. The connector name and a link to the vendor's connector or MCP documentation
2. Your business use case  describe how you plan to use the integration and what problem it solves
3. Confirmation of an SU contract or agreement with the vendor, if applicable
4. A SOC 2 Type II report from the vendor, or confirmation that you can obtain one

## What We Review Before Approving a Connector

ITS evaluates connector requests based on several key factors.

**Security Compliance:** The most important requirement is that the third-party vendor can provide a SOC 2 Type II audit report. This confirms the vendor has adequate security controls for handling university data. Many vendors publish this on a trust page or you can request it from your account representative. Requests will be on hold until this documentation is provided.

**Existing University Relationship:** Connectors for tools where SU already has a contract are easier to approve. If your department uses a tool through a university-wide agreement, that supports the case for enabling its connector.

**Data Classification Risk:** We consider what kind of university data may flow through the connector. Connectors that could expose Confidential data such as FERPA records, HIPAA data, PII, or financial information face a higher bar for approval and may require additional security review.

**Breadth of Use:** Because connectors are enabled at the organization level, ITS weighs whether a connector benefits a broader population of SU users versus a single individual or team. Highly specialized tools with limited campus use may be deprioritized.

**Vendor Maturity:** We look at whether the vendor's MCP or connector implementation is well-supported. Early-stage or experimental integrations may be held until they stabilize.

## What Could Prevent Approval

A request is unlikely to be approved if the vendor cannot provide a SOC 2 Type II report, if SU has no existing contract with the vendor, if the tool is not approved for use with university data, if the connector would expose restricted data without adequate controls, or if the functionality is already available through an existing approved connector.

## Frequently Asked Questions

**Can I use a connector that is not on the approved list?**
Not through the university Claude instance. Connectors must be reviewed and enabled by ITS before they appear in your Claude settings. Submit a request to [aihelp@syr.edu](mailto:aihelp@syr.edu).

**How long does the review take?**
It depends on how quickly vendor documentation can be obtained. Simple requests where a SOC 2 report is readily available may resolve within a few business days. More complex reviews take longer.

**What if my vendor does not have a SOC 2 report?**
ITS will work with you to assess alternatives, but in some cases the request may not be approvable under current policy.

**Can I use connectors in Claude Desktop that are not enterprise-enabled?**
Claude Desktop supports local MCP connections that run entirely on your machine without transmitting data to a third-party server. These local integrations may be appropriate for certain use cases.

## Questions?

Reach out to the AI team at [aihelp@syr.edu](mailto:aihelp@syr.edu) or book a consultation at the AI at Syracuse University Bookings page.
