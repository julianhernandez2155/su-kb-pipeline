---
page_id: '986841103'
title: Claude Code Setup
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/986841103/Claude+Code+Setup
space_key: ITSAI
space_name: Artificial Intelligence (AI)
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path:
- AI @ Syracuse University
- AI
- Claude
last_modified: '2026-04-15T16:52:50.033Z'
version: 19
contributors:
- 712020:882951bc-9249-4b41-8242-4d19030b3116
contributors_count: 1
content_hash: sha256:b27e7a6f07f056fa8c90da7879f8ebe5671072c0a0eb3d045c577fe1bd445d67
synced_at: '2026-05-13T16:56:22Z'
last_sync_status: ok
labels: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 28
maintenance_signal: fresh
conversion_warnings: []
---

# Step 1: Get access to Claude Code

Using one of the methods for obtaining Claude Code described on the page: [[540934169 - Purchase Claude Code and Claude API Access|Purchase Claude Code and Claude API Access - Artificial Intelligence (AI) - Answers]]

# Step 2: Install Claude Code & Development Tools

An automated PowerShell script for Windows (`Install-DevTools.ps1`) downloads and configures portable versions of all required development tools. The script auto-detects your system architecture (AMD64 or ARM64) and downloads the appropriate installers. It's idempotent, so it's safe to run multiple times.

### What Gets Installed

| **Tool** | **Version** | **Notes** |
| --- | --- | --- |
| Node.js | 24.12.0 | Portable/embedded |
| Git Portable | 2.52.0 | Includes Git Bash |
| Python Embeddable | 3.14.3 | pip-enabled; skipped if system Python detected |
| VS Code Portable | Latest | Skipped if already installed on the system |
| GitHub Desktop | Latest | Visual interface for Git version control |
| PowerShell 7 | Latest | Installed via winget from Microsoft Store; skipped if already installed |
| Claude Code | Latest | Always installs locally; requires Git first |

### Where Tools Install

By default, tools install to your **OneDrive** for automatic sync across devices. Claude Code always installs locally regardless of this setting.

| **Location** | **Path** |
| --- | --- |
| OneDrive (default) | `%OneDrive%\Apps-SU\[arch]\<ToolName>` |
| Local | `%USERPROFILE%\Apps-SU\[arch]\<ToolName>` |
| Claude Code (always) | `%USERPROFILE%\.local\bin` |

Tools are organized into architecture-specific subdirectories to prevent conflicts when OneDrive syncs across devices with different architectures:

```
Apps-SU\
├── AMD64\
│   ├── Node\
│   ├── PortableGit\
│   ├── Python\
│   └── VSCode\
└── ARM64\
    ├── Node\
    ├── PortableGit\
    ├── Python\
    └── VSCode\
```

## Set Execution Policy

Before running the script, open PowerShell and run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Download & Run the Install Script

Download the script, save it as `Install-DevTools.ps1`

[Install-DevTools.ps1](attachments/986841103/Install-DevTools.ps1)

## Remove the Mark of the Web

When you download a file from the internet, Windows tags it with a "Mark of the Web" (MOTW) that blocks it from running, even if your execution policy is set to RemoteSigned. You need to unblock the file before running it.

**Option 1: PowerShell command (recommended)**

Open PowerShell and run:

```powershell
Unblock-File -Path "$HOME\Downloads\Install-DevTools.ps1"
```
Adjust the path if you saved the file somewhere other than your Downloads folder.

**Option 2: File Properties**

1. Right-click the downloaded `Install-DevTools.ps1` file in File Explorer
2. Select **Properties**
3. At the bottom of the General tab, check the **Unblock** checkbox
4. Click **OK**

### Run the Script

Run it from PowerShell:

```powershell
# Install all tools to OneDrive (default)
.\Install-DevTools.ps1
```

# Step 3: Configure Claude Code

Once installation is complete, follow these steps to connect Claude Code to your Syracuse University account

1. **Launch Claude Code.** Open a terminal and type:

```
claude
```
1. **Choose your text display style.** Select whichever option you prefer.
2. **Select "Anthropic Console account"** (option 2) when prompted for your login method.
3. **Sign in.** A browser window will open, and sign in with your `netid@syr.edu` credentials. If prompted, select the **Syracuse University** organization.
4. **Authorize Claude Code** when prompted in the browser.
5. **Return to the terminal** and press Enter twice to accept and trust the folder

**You're all set!**

Claude Code is now ready to use. Start by asking it a question or giving it a task in the terminal.

# Optional: GitHub

GitHub is an excellent companion to Claude Code. When Claude Code makes changes to your files, Git tracks every modification so you can see exactly what was added, removed, or changed. This is especially valuable when working with an AI coding tool because it gives you a clear record of what Claude did and makes it easy to undo any changes you don't want to keep.

**Why use Git with Claude Code?**

Git gives you a safety net when letting Claude Code work on your files. Before you ask Claude to make changes, you can commit your current work. After Claude finishes, you can review a line-by-line diff of everything it touched. If something doesn't look right, you can revert back to your previous commit in seconds. Without Git, you would have no easy way to see what changed or roll things back.

Git also makes it practical to experiment. You can create a branch, let Claude Code try an approach, and if it doesn't work out, simply switch back to your main branch. This encourages you to use Claude Code more boldly, knowing you can always get back to a known good state.

**Getting started with GitHub**

[GitHub at Syracuse University](https://answers.atlassian.syr.edu/wiki/search?text=GitHub+at+Syracuse+University&spaceKey=ITHELP)

# Optional: VS Code Integration

For an enhanced development experience, you can integrate Claude Code with Visual Studio Code. Follow the official documentation:

[Claude Code VS Code Integration Guide](https://code.claude.com/docs/en/vs-code)

# Troubleshooting

This problem typically arises when the script is downloaded from the web (as opposed to cloning the repo via Git). Windows applies a "Mark of the Web" to downloaded files, which blocks PowerShell from executing them. To fix this, unblock the file using one of the methods described in Step 2 above. If you prefer not to unblock the file, you can also bypass the execution policy for a single session:

In PowerShell:

`Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`

From the Command Prompt (cmd):

`powershell -ExecutionPolicy Bypass -File .\Install-DevTools.ps1`

The script only supports AMD64 and ARM64. 32-bit systems are not supported.

Restart your terminal or PowerShell session.

The script checks `OneDriveCommercial` and `OneDrive` environment variables. Use `-Location Local` if OneDrive is unavailable.

Verify internet connectivity. Some corporate networks may block downloads.

Supported formats: ZIP and self-extracting EXE (7z syntax).

The script configures registry compatibility settings automatically. If issues persist, verify the registry entry at:

`HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers`

You should see a registry Name similar to: `C:\Users\USERNAME\.local\bin\claude.exe` With a Data value of `~ ARM64HIDEAVX`
