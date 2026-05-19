---
page_id: '988774401'
title: Working with SharePoint Files in Claude
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/988774401/Working+with+SharePoint+Files+in+Claude
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
last_modified: '2026-04-16T14:17:41.955Z'
version: 1
contributors:
- 712020:80f8cb27-5c7e-4ff8-ae31-4211dd953797
contributors_count: 1
content_hash: sha256:d6d9c8d443ca38177835fd02b62c2755c87247f648cd396ee5f7c11d312161a1
synced_at: '2026-05-19T15:04:30Z'
last_sync_status: ok
labels: []
tags_original: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 33
maintenance_signal: fresh
word_count: 390
char_count: 2441
token_estimate: 698
attachment_count: 3
conversion_warnings: []
---

Claude can find, read, and edit files stored in SharePoint  including adding new entries, updating content, and creating new files. The key is connecting your SharePoint folder to your computer via a**OneDrive shortcut**, then granting Claude access to that folder using the **Filesystem connector** in the Claude Desktop app.

> [!info]
> The Filesystem connector requires the **Claude Desktop app**. If you only use Claude in the browser, you can dowload the desktop app via <https://claude.com/download>.

## Filesystem Connector Capabilities

| **Action** | **Filesystem Connector Capability** |
| --- | --- |
| Read files in your shortcutted SharePoint folders | ✅ |
| Find files by name in shortcutted folders | ✅ |
| Edit or update existing files | ✅ |
| Create new files | ✅ |
| Delete files | ❌ |
| Search across all SharePoint sites (not just shortcutted ones) | ❌ |
| Access Outlook email, calendar, and Teams | ❌ |
| Works in the browser | ❌ |

## Step 1: Add Your SharePoint Folder as a Shortcut in OneDrive

- Open your **SharePoint site** in a web browser and navigate to the folder that has the files you want Claude to work with.
- Click the **Add shortcut to My files** button in the toolbar at the top of the page.
- You'll see a confirmation message. You can find it in **File Explorer** (Windows) or **Finder** (Mac) under your **OneDrive - Syracuse University** folder. It will have a small shortcut arrow on the icon.

![[attachments/988774401/Screenshot 2026-04-15 162826.jpg|760]]

## Step 2:  Enable the Filesystem Connector in Claude Desktop

- Open the **Claude Desktop app**. If you haven't installed it yet, download it at <https://claude.com/download> and sign in with your SU credentials.
- Find **Filesystem** in the connector list, then install and enable it.

![[attachments/988774401/image.png|420]]

- When configuring, **paste the**SharePoint shortcut path in the directory path. This is usually something like `C:\Users\YourName\OneDrive - Syracuse University` on Windows or `~/OneDrive - Syracuse University` on Mac. You can select the whole OneDrive folder or just the specific shortcut folder. You can add multiple paths.

![[attachments/988774401/image (1).png|282]]

Give it a try, Claude can now read and edit SharePoint files for you.

---

## Questions?

Reach out to the AI team at [aihelp@syr.edu](mailto:aihelp@syr.edu) or book a consultation at the AI at Syracuse University Bookings page.
