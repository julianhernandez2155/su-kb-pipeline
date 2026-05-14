---
page_id: '591101962'
title: mentorAI - Using the API
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/591101962/mentorAI+-+Using+the+API
space_key: ITSAI
space_name: Artificial Intelligence (AI)
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path:
- AI @ Syracuse University
- AI
- Clementine Platform
last_modified: '2026-03-05T17:04:37.341Z'
version: 22
contributors:
- 712020:4c323a6a-283a-4261-80da-1e662db12cda
contributors_count: 1
content_hash: sha256:0207e9a09c3b230164ce6bff8e482ffaf405f03b8d21616842734277aba253cf
synced_at: '2026-05-13T16:56:06Z'
last_sync_status: ok
labels: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 68
maintenance_signal: fresh
conversion_warnings: []
---

> [!note]
> This document is still under construction, thank you for your patience.

## Overview

This document is designed to provide starting point with interacting with mentorAI via its API and programmatically.

---

## Interacting with the API

There are many ways to interact with an API and below are two examples, and how to set their environments up.

### VS Code

Visual Studios Code is the light version of Visual Studios. It provides a powerful environment to program from and is the recommended IDE to use.

[Setting up VS Code](https://answers.atlassian.syr.edu/wiki/x/BQA8Iw)

---

## API Methods

In short, an API method is the basic idea of what you want an API to do. If all you wish to do is get information in regards to something you would use GET as the method. If you wish to create something new or request the API to make something, you would likely use a POST method.

---

## Getting an API Key

> [!info]
> Despite an API key appearing as an option on a mentor, it is actually tied to your account, not a specific mentor. The API key has the same permissions your user account does.

At this time, request access to the API by emailing [aihelp@syr.edu](mailto:aihelp@syr.edu) with your username (netid) and please provide a brief description of what you plan to use the API for so we know different use cases for the product.

1. Afterwards, log back into mentorAI and navigate to a mentor you created or have been granted access to and select the API action in the drop down.

![[attachments/591101962/image-20251118-141734.png|146]]

1. Press the Create New button

   1. Provide a name that is concise but descriptive of the keys use-case
   2. Pick an expiration date. Common intervals are 1 month, 3 months, 1 year.
   3. Press Submit
2. Copy the string that is now provided to you. This string will **NOT** be shown to you again. This string is your API key/token. Do **NOT** share it with anyone. Store the string somewhere safe, like a password manager.

> [!note]
> When programming, do **NOT** place your API key directly in your code. Instead, place it somewhere else and pull it into the code. Such as storing it in a .txt file and reading the file in the code.
>
> If you use GitHub, be sure to not accidently upload your key into your repository!

---

## API Documentation

IBL (the creators of mentorAI) have a documentation resource that you may find useful. See the links below:

[ibl-data-manager (Public)](https://docs.ibl.ai/apis/ibl.3.59.0/)

---

## Examples

Currently the examples are in the PowerShell language.

> [!info]
> In the future, our examples may be moved to GitHub or another method, and links will be provided. This will be to offer more programming language support for each example.

### Get Mentors

To get the mentors you have created, you will need to interact with a separate endpoint at this time. It is commented out in the code block below and shown here:

```
$urlPathway = https://base.manager.ai.syr.edu/api/ai-search/personalized-mentors/?platform_key=$orgId
```

```powershell
$ErrorActionPreference = 'Stop'

#=== GET API KEY FROM FILE ===
[System.String]$apiKey = (Get-Content -Path "C:\path\to\your\apikey.txt" -Raw).Trim()

#=== BUILD REQUEST HEADERS ===
$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Api-Token $apiKey"
}

[System.String]$orgId = "syracuse"
[System.String]$userId = "{INSERT YOUR NETID HERE}" #can also use your FID

#=== API URL TO GET ALL MENTORS FOR A USER ===
# Below are multiple methods and examples of API endpoints to accomplish this goal

# Get the list of mentors you have access to.
#$urlPathway = "https://base.manager.ai.syr.edu/api/ai-mentor/orgs/$orgid/users/$userid/"

# Get the list of mentors you have access to, but pre-sort the response by name of the mentor
#$urlPathway = "https://base.manager.ai.syr.edu/api/ai-mentor/orgs/$orgid/users/$userid/?filter_by=name"

# Get the list of mentors created by a user (may require a user's FID as opposed to their netid)
#$urlPathway = "https://base.manager.ai.syr.edu/api/ai-search/mentors/?platform_key=$orgId&created_by=$userid"

# Similar to the first example, Get a list of mentors you have access to
$urlPathway = "https://base.manager.ai.syr.edu/api/ai-search/mentors/?platform_key=$orgId"

# Get the specific mentors you have created
#$urlPathway = "https://base.manager.ai.syr.edu/api/ai-search/personalized-mentors/?platform_key=$orgId"

#=== CALL THE API ===
try {
    $response = Invoke-RestMethod -Uri $urlPathway -Method Get -Headers $headers
    $response.results | Format-List
}
catch {
    Write-Host "StatusCode:" $_.Exception.Response.StatusCode.value__
    Write-Host "StatusDescription:" $_.Exception.Response.StatusDescription
    Write-Host $_.Exception
    exit
}
```

### Get Mentor Datasets

```powershell
$ErrorActionPreference = 'Stop'

#=== GET API KEY FROM FILE ===
[System.String]$apiKey = (Get-Content -Path "C:\path\to\your\apikey.txt" -Raw).Trim()

#=== BUILD REQUEST HEADERS ===
$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Api-Token $apiKey"
}

[System.String]$orgId = "syracuse"
[System.String]$userId = "{INSERT YOUR NETID HERE}" #can also use your FID
[System.String]$pathway = "{INSERT MENTOR STRING HERE}" #You can find this at the end of the URL string when viewing a mentor in a browser. Will be formatted like: 12345678-1234-1234-1234-123456789012

#=== API URL TO GET ALL DATASETS FOR A PATHWAY ===
$urlPathway = "https://base.manager.ai.syr.edu/api/ai-index/orgs/$orgid/users/$userid/documents/pathways/$pathway/"

#=== CALL THE API ===
try {
    $response = Invoke-RestMethod -Uri $urlPathway -Method Get -Headers $headers
    $response.results | Format-List
}
catch {
    Write-Host "StatusCode:" $_.Exception.Response.StatusCode.value__
    Write-Host "StatusDescription:" $_.Exception.Response.StatusDescription
    Write-Host $_.Exception
    exit
}
```

### Upload a document to a Mentor (Upload a dataset)

```powershell
$ErrorActionPreference = 'Stop'

#=== GET API KEY FROM FILE ===
[System.String]$apiKey = (Get-Content -Path "C:\path\to\your\apikey.txt" -Raw).Trim()

#=== BUILD REQUEST HEADERS ===
$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Api-Token $apiKey"
}

[System.String]$orgId = "syracuse"
[System.String]$userId = "{INSERT YOUR NETID HERE}" #can also use your FID
[System.String]$url = "https://base.manager.ai.syr.edu/api/ai-index/orgs/$orgId/users/$userId/documents/train/"

[System.String]$pathway = "{INSERT MENTOR STRING HERE}" #You can find this at the end of the URL string when viewing a mentor in a browser. Will be formatted like: 12345678-1234-1234-1234-123456789012
[System.String]$ingestURL = "{ENTER URL OF PUBLIC WEBSITE YOU WISH TO UPLOAD HERE}"

$body = @{
    "pathway" = $pathway
    "url" = $ingestURL
    "type" = "url"
    "access" = "private"
} | ConvertTo-Json

#=== CALL THE API ===
try
{
    $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body
}
catch
{
    Write-Host "StatusCode:" $_.Exception.Response.StatusCode.value__
    Write-Host "StatusDescription:" $_.Exception.Response.StatusDescription
    Write-Host $_.Exception
    exit
}

Write-Host $response.message
Write-Host "Task ID:" + $response.task_id
Write-Host "Doc ID: " + $response.document_id
```

### Create chat session with Mentor

> [!info]
> Use this code below to get a sessionId. Then use the sessionId in the code to send a chat message. You can also get a sessionId from the developer tools in a browser. Steps are explained after the code for sending a message.

```powershell
$ErrorActionPreference = 'Stop'

#=== GET API KEY FROM FILE ===
[System.String]$apiKey = (Get-Content -Path "C:\path\to\your\apikey.txt" -Raw).Trim()

#=== BUILD REQUEST HEADERS ===
$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Api-Token $apiKey"
}

[System.String]$orgId = "syracuse"
[System.String]$userId = "{INSERT YOUR NETID HERE}" #can also use your FID
[System.String]$mentorName = "{INSERT NAME OF THE MENTOR HERE}"
[System.String]$url = "https://base.manager.ai.syr.edu/api/ai-mentor/orgs/$orgId/users/$userId/sessions/"

$body = @{
  "mentor" = $mentorName
} | ConvertTo-Json

#=== CALL THE API ===
try
{
    $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body
    $sessionId = $response[0].session_id
}
catch
{
    Write-Host "StatusCode:" $_.Exception.Response.StatusCode.value__
    Write-Host "StatusDescription:" $_.Exception.Response.StatusDescription
    Write-Host $_.Exception
    exit
}
```

### Send a chat message to a mentor

> [!info]
> We are working on trying to set it up so you can use the API to talk with a mentor rather than going through a web socket. Thank you for your patience
>
> We have an SSE connection as a possibility as well, this would still require an access code, but may be useful depending on your scenario. Please reach out to us if you are interested in an example to connect via SSE.

```powershell
$ErrorActionPreference = 'Stop'

[System.String]$sessionId = "12345678-1234-1234-1234-1234567890"  # From the previous code
[System.String]$orgId = "syracuse"
[System.String]$userId = "{INSERT YOUR FID HERE}" # See information below this code snippet on how to obtain this
[System.String]$pathway = "{INSERT MENTOR STRING HERE}" #You can find this at the end of the URL string when viewing a mentor in a browser. Will be formatted like: 12345678-1234-1234-1234-123456789012
[System.String]$prompt = "Hello, what's your name?"

# Step 2: Create the JSON payload
$payload = @{
    flow = @{
        name = $pathway
        tenant = $orgId
        username = $userId
        pathway = $pathway
    }
    session_id = $sessionId
    token = "{INSERT TOKEN STRING HERE}" # See information below this code snippet on how to obtain this
    prompt = $prompt
} | ConvertTo-Json

# Step 3: Create and connect a webSocket
[System.Net.WebSockets.ClientWebSocket]$ws = New-Object System.Net.WebSockets.ClientWebSocket
$uri = [System.Uri]::new("wss://asgi.data.ai.syr.edu/ws/langflow/")
[System.Threading.CancellationTokenSource]$cts = New-Object System.Threading.CancellationTokenSource

try {
    # Connect to WebSocket
    #Write-Host "Connecting to WebSocket..." -ForegroundColor Yellow
    $connectTask = $ws.ConnectAsync($uri, $cts.Token)
    $connectTask.Wait()
    #Write-Host "Connected!" -ForegroundColor Green

    # Step 4: Send the message
    #Write-Host "Sending message..." -ForegroundColor Yellow
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $buffer = New-Object System.ArraySegment[byte] -ArgumentList @(,$bytes)
    $sendTask = $ws.SendAsync($buffer, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token)
    $sendTask.Wait()
    #Write-Host "Message sent!" -ForegroundColor Green

    # Step 5: Receive responses
    #Write-Host "`nReceiving responses:" -ForegroundColor Yellow
    $fullResponse = ""

    $receiveBuffer = New-Object byte[] 4096
    $segment = New-Object System.ArraySegment[byte] -ArgumentList @(,$receiveBuffer)

    do {
        $receiveTask = $ws.ReceiveAsync($segment, $cts.Token)
        $receiveTask.Wait()
        $result = $receiveTask.Result

        $message = [System.Text.Encoding]::UTF8.GetString($receiveBuffer, 0, $result.Count)
        $jsonResponse = $message | ConvertFrom-Json

        # Display the response
        #Write-Host $message

        # If it's a data chunk, accumulate it
        if ($jsonResponse.type -eq $null -and $jsonResponse.data) {
            $fullResponse += $jsonResponse.data
        }

        # Check if we've reached the end of responses
        if ($jsonResponse.eos -eq $true) {
            break
        }

    } while ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open)

    # Display the completed response
    #Write-Host "`n`nComplete Response:" -ForegroundColor Cyan
    Write-Host $prompt
    Write-Host $fullResponse

} catch {
    Write-Host "Error: $_" -ForegroundColor Red
} finally {
    # Step 6: Clean up
    if ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $cts.Token).Wait()
    }
    $ws.Dispose()
    $cts.Dispose()
    #Write-Host "`nWebSocket closed." -ForegroundColor Yellow
}
```

#### Getting a token and your FID

We are working on a way to programmatically get a token, however, at this time, you can get one from your web browser. Follow the steps outlined below:

> [!note]- Steps
> 1. Navigate to [mentorAI](https://mentor.ai.syr.edu/platform/syracuse)
> 2. Go to a mentor you are the creator or have permission to
> 3. Open the developer tools for the web browser you are using
>
>    1. Such as `F12` or `Ctrl + Shift + I` on a Windows computer
>    2. `Fn + F12` or `Command + Option + I` on a Mac computer
> 4. Send a chat message to the mentor, you can ask it anything.
> 5. Go to the Network tab  filter on Socket (might be called WS, WebSocket, etc)  select langflow/
>
>    1. Make sure you are on the Messages tab to the right of langflow/
> 6. Look at a message and grab the FID (username) and the Token that was used.
>
>    ![[attachments/591101962/image-20251124-142630.png|655]]
