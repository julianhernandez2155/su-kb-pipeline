---
page_id: '837517313'
title: Claude Local MCP - Connecting Claude Desktop to Power BI
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/837517313/Claude+Local+MCP+-+Connecting+Claude+Desktop+to+Power+BI
space_key: ITSAI
space_name: Artificial Intelligence (AI)
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path:
- AI @ Syracuse University
- AI
- Claude
last_modified: '2026-02-20T20:46:04.702Z'
version: 2
contributors:
- 712020:80f8cb27-5c7e-4ff8-ae31-4211dd953797
contributors_count: 1
content_hash: sha256:63f3e08e721f2b789f1937a797b309ca379fb268afc7c43b695d4be382800261
synced_at: '2026-05-13T16:56:16Z'
last_sync_status: ok
labels: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 81
maintenance_signal: fresh
conversion_warnings: []
---

---

# **What is Local MCP?**

Claude local MCP (Model Context Protocol) is an open-source standard developed by Anthropic that allows the Claude Desktop app to securely connect to, read, and interact with data and tools directly on your local computer, such as files, folders, databases, and APIs. It enables AI-driven automation, allowing Claude to perform actions like editing code, querying local data, or interacting with software tools without leaving your desktop interface.

---

# Using Power BI MCP as an example

1. Download MCP from VS Code

Search for the Power BI Modeling MCP extension from VS Code, and download the one published by Microsoft.

![[attachments/837517313/image-20260220-192341.png|760]]

1. Fine the powerbi-modeling-mcp.exe file from the VS Code extension file. You can find it from a similar file path:

```
C:\Users\<YourUsername>\.vscode\extensions\analysis-services.powerbi-modeling-mcp-0.1.9-win32-x64\server
```
![[attachments/837517313/image-20260220-192904.png|760]]

1. Hold shift, right-click the exe file, and copy as path, save it somewhere for later use
2. Open the Claude desktop APP, click the edit config button as shown below

![[attachments/837517313/image-20260220-193155.png|760]]

1. Open the config file in VS Code, paste the configuration below, and save it

```
{
  "mcpServers": {
    "powerbi-modeling-mcp": {
      "command": "paste the path you copied before here",
      "args": ["--start"],
      "env": {}
    }
  }
}
```
> [!info]
> Remember to use double backslashes (\\) instead of single ones (\) in the path.

1. Reboot the computer, then open the Claude desktop APP. You should see the MCP added to the Claude.

![[attachments/837517313/image-20260220-194005.png|760]]

> [!info]
> For adding more mcps, you can use simialr measure by using , seperating them see example below

```
{
  "mcpServers": {
    "powerbi-modeling-mcp": {
      "command": "your path",
      "args": ["--start"],
      "env": {}
    }
  },
"mcpServers": {
    "other mcp": {
      "command": "your path",
      "args": ["--start"],
      "env": {}
    }
  }
}
```

---

# How to use it?

Now, you can open any Power BI report you are working on and open a chat from Claude Desktop. Input the prompt

> *Connect to the open Power BI desktop file*
From here, Claude will do its magic.

![[attachments/837517313/image-20260220-195700.png|760]]

![[attachments/837517313/image-20260220-195824.png|760]]

> [!info]
> You are in control of how much access Claude can have.
