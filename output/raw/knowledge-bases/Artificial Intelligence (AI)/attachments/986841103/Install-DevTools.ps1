<#
.SYNOPSIS
    Downloads and installs portable development tools to user-scoped OneDrive or Local folder.
.DESCRIPTION
    Automatically downloads, extracts, and configures portable versions of development tools
    (Node.js, Git, Python, VS Code, Claude Code, GitHub Desktop, PowerShell 7) to either OneDrive\Apps-SU\[arch] or Local\Apps-SU\[arch].
    GitHub Desktop is always installed locally to %LOCALAPPDATA%\GitHubDesktop regardless of the Location parameter.
    PowerShell 7 is installed via winget from the Microsoft Store (per-user, no admin required).
    Updates USER PATH as needed and cleans up installation files.

    Detects system architecture (x64 or ARM64) and downloads the appropriate installers.
    Organizes tools in architecture-specific subdirectories to prevent conflicts on shared drives.
    Before installing, checks if tools are already installed in either location.
.PARAMETER Tools
    Array of tool names to install. If not specified, installs all available tools.
    A Prerequisite to ClaudeCode is Git. If only ClaudeCode is specified, Git will be added to the list to install as well.
    Valid values: 'Node', 'Git', 'Python', 'VSCode', 'ClaudeCode', 'GitHubDesktop', 'PowerShell7', 'All'
.PARAMETER Location
    Where to install tools. Options: 'OneDrive' (default) or 'Local'
    Note: Claude Code is always installed locally regardless of this setting.
.PARAMETER SkipPathUpdate
    If specified, skips updating the USER PATH environment variable.
.PARAMETER Quiet
    If specified, suppresses informational output (errors and warnings still shown).
.EXAMPLE
    .\Install-DevTools.ps1
    Installs all available tools to OneDrive.
.EXAMPLE
    .\Install-DevTools.ps1 -Location Local
    Installs all tools locally.
.EXAMPLE
    .\Install-DevTools.ps1 -Tools 'Node','Git','ClaudeCode' -Location OneDrive
    Installs Node and Git to OneDrive, Claude Code locally.
.NOTES
    - Claude Code MUST be installed after Git
    - Git installation sets CLAUDE_CODE_GIT_BASH_PATH environment variable
    - Claude Code installation requires a new PowerShell session or PATH refresh
    - Automatically detects and handles both x64 and ARM64 architectures
#>
[CmdletBinding(DefaultParameterSetName = 'Default')]
Param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('Node', 'Git', 'Python', 'VSCode', 'ClaudeCode', 'GitHubDesktop', 'PowerShell7', 'All')]
    [string[]]$Tools = @('All'),

    [Parameter(Mandatory = $false)]
    [ValidateSet('OneDrive', 'Local')]
    [string]$Location = 'OneDrive',

    [Parameter(Mandatory = $false)]
    [switch]$SkipPathUpdate,

    [Parameter(Mandatory = $false)]
    [switch]$Quiet
)

begin {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = [System.Management.Automation.ActionPreference]::Stop
    $WarningPreference = [System.Management.Automation.ActionPreference]::SilentlyContinue
    $ProgressPreference = [System.Management.Automation.ActionPreference]::SilentlyContinue

    $script:OneDriveRoot = $null
    $script:OneDriveAppsRoot = $null
    $script:LocalRoot = $null
    $script:LocalAppsRoot = $null
    $script:LocalGitRoot = $null
    $script:AppsRoot = $null  # Will be set based on Location parameter
    $script:TempDownloadFolder = $null
    $script:IsArm64 = $false

    #region Initialize-ToolConfigs

    function Initialize-ToolConfigs {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [bool]$IsArm64
        )

        if ($IsArm64) {
            $nodeUrl = 'https://nodejs.org/dist/v24.12.0/node-v24.12.0-win-arm64.zip'
            $gitUrl = 'https://github.com/git-for-windows/git/releases/download/v2.52.0.windows.1/PortableGit-2.52.0-arm64.7z.exe'
            $pythonUrl = 'https://www.python.org/ftp/python/3.14.3/python-3.14.3-embed-arm64.zip'
            $vsCodeUrl = 'https://code.visualstudio.com/sha/download?build=stable&os=win32-arm64-archive'
            $githubDesktopUrl = 'https://central.github.com/deployments/desktop/desktop/latest/win32-arm64'
        } else {
            $nodeUrl = 'https://nodejs.org/dist/v24.12.0/node-v24.12.0-win-x64.zip'
            $gitUrl = 'https://github.com/git-for-windows/git/releases/download/v2.52.0.windows.1/PortableGit-2.52.0-64-bit.7z.exe'
            $pythonUrl = 'https://www.python.org/ftp/python/3.14.3/python-3.14.3-embed-amd64.zip'
            $vsCodeUrl = 'https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-archive'
            $githubDesktopUrl = 'https://central.github.com/deployments/desktop/desktop/latest/win32'
        }

        $script:ToolConfigs = @{
            Node = @{
                Name = 'Node.js'
                DownloadUrl = $nodeUrl
                FolderName = 'Node'
                PathSubfolder = ''
                AdditionalPaths = @()
                FlattenArchive = $true
                PostInstallScript = $null
                UseOfficialInstaller = $false
                ExecutablesToCheck = @("node.exe")
            }
            Git = @{
                Name = 'Git Portable'
                DownloadUrl = $gitUrl
                FolderName = 'PortableGit'
                PathSubfolder = 'cmd'
                AdditionalPaths = @('bin', 'usr\bin')
                FlattenArchive = $false
                UseOfficialInstaller = $false
                ExecutablesToCheck = @("cmd\git.exe", "bin\bash.exe")
                PostInstallScript = {
                    param($ToolPath)
                    # Set CLAUDE_CODE_GIT_BASH_PATH for Claude Code
                    $bashPath = Join-Path $ToolPath "bin\bash.exe"
                    if (Test-Path -LiteralPath $bashPath) {
                        [Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $bashPath, "User")
                        $env:CLAUDE_CODE_GIT_BASH_PATH = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")
                        Write-Log "Set CLAUDE_CODE_GIT_BASH_PATH to: $bashPath"
                    } else {
                        Write-Log "Warning: bash.exe not found at expected location: $bashPath" -Level Warning
                    }
                }
            }
            ClaudeCode = @{
                Name = 'Claude Code'
                DownloadUrl = $null
                FolderName = 'ClaudeCode'
                PathSubfolder = ''
                AdditionalPaths = @()
                FlattenArchive = $false
                UseOfficialInstaller = $true
                ExecutablesToCheck = @("claude.exe")
                RequiresGit = $true  # Flag that Git must be installed first
            }
            Python = @{
                Name = 'Python Embeddable'
                DownloadUrl = $pythonUrl
                FolderName = 'Python'
                PathSubfolder = ''
                AdditionalPaths = @('Scripts')
                FlattenArchive = $false
                UseOfficialInstaller = $false
                ExecutablesToCheck = @("python.exe", "pythonw.exe")
                PostInstallScript = {
                    param($ToolPath)
                    # Enable pip in embeddable Python
                    $pthFile = Get-ChildItem -Path $ToolPath -Filter "*._pth" | Select-Object -First 1
                    if ($pthFile) {
                        $content = Get-Content $pthFile.FullName
                        $content = $content -replace '^#import site', 'import site'
                        Set-Content -Path $pthFile.FullName -Value $content
                    }
                    # Create Scripts folder
                    $scriptsPath = Join-Path $ToolPath 'Scripts'
                    if (-not (Test-Path $scriptsPath)) {
                        New-Item -Path $scriptsPath -ItemType Directory -Force | Out-Null
                    }
                }
            }
            VSCode = @{
                Name = 'VS Code Portable'
                DownloadUrl = $vsCodeUrl
                FolderName = 'VSCode'
                PathSubfolder = 'bin'
                AdditionalPaths = @()
                FlattenArchive = $true
                UseOfficialInstaller = $false
                ExecutablesToCheck = @("bin\code.cmd")
                PostInstallScript = {
                    param($ToolPath)
                    # Create 'data' folder for portable mode
                    $dataFolder = Join-Path $ToolPath "data"
                    if (-not (Test-Path $dataFolder)) {
                        New-Item -Path $dataFolder -ItemType Directory -Force | Out-Null
                    }
                }
            }
            GitHubDesktop = @{
                Name = 'GitHub Desktop'
                DownloadUrl = $githubDesktopUrl
                FolderName = 'GitHubDesktop'
                PathSubfolder = ''
                AdditionalPaths = @()
                FlattenArchive = $false
                UseOfficialInstaller = $true
                ExecutablesToCheck = @("GitHubDesktop.exe")
                PostInstallScript = $null
            }
            PowerShell7 = @{
                Name = 'PowerShell 7'
                DownloadUrl = $null  # Installed via winget
                FolderName = 'PowerShell7'
                PathSubfolder = ''
                AdditionalPaths = @()
                FlattenArchive = $false
                UseOfficialInstaller = $true
                ExecutablesToCheck = @("pwsh.exe")
                PostInstallScript = $null
            }
        }
    }

    #endregion Initialize-ToolConfigs
    #region Write-Log

    function Write-Log {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string]$Message,

            [Parameter(Mandatory = $false)]
            [ValidateSet('Info', 'Warning', 'Error', 'Success')]
            [string]$Level = 'Info'
        )

        if ($Quiet -and $Level -eq 'Info') { return }

        switch ($Level) {
            'Warning' { Write-Warning $Message }
            'Error' { Write-Error $Message }
            'Success' { Write-Host $Message -BackgroundColor Yellow -ForegroundColor Black }
            default { Write-Host $Message }
        }
    }

    #endregion Write-Log
    #region Initialize-Environment

    function Initialize-Environment {
        [CmdletBinding()]
        param()

        # Check architecture using reliable CIM method
        [bool]$isArm = (Get-CimInstance Win32_Processor | Select-Object Architecture).Architecture -contains 12
        
        if ($isArm) {
            $script:IsArm64 = $true
            [System.String]$Architecture = 'ARM64'
            Write-Log "Using ARM64 installers"
        } else {
            $script:IsArm64 = $false
            [System.String]$Architecture = 'AMD64'
            Write-Log "Using x64 installers"
        }

        # Initialize tool configs based on architecture
        Initialize-ToolConfigs -IsArm64 $script:IsArm64

        # Set up OneDrive paths
        $oneDrive = $env:OneDriveCommercial
        if (-not $oneDrive) { $oneDrive = $env:OneDrive }
        if (-not $oneDrive) { $oneDrive = [Environment]::GetEnvironmentVariable("OneDriveCommercial", "User") }
        if (-not $oneDrive) { $oneDrive = [Environment]::GetEnvironmentVariable("OneDrive", "User") }

        if ($oneDrive) {
            $script:OneDriveRoot = $oneDrive
            $script:OneDriveAppsRoot = Join-Path $oneDrive "Apps-SU\$Architecture"
            Write-Log "OneDrive Root: $script:OneDriveRoot"
            Write-Log "OneDrive Apps Root: $script:OneDriveAppsRoot"
        } else {
            Write-Log "OneDrive not found - Local installation only" -Level Warning
        }

        # Set up Local paths
        $localPath = $env:USERPROFILE
        if (-not $localPath) { $localPath = $HOME }

        if (-not $localPath) {
            throw "Unable to locate UserProfile folder"
        }

        $script:LocalRoot = $localPath
        $script:LocalAppsRoot = Join-Path $localPath "Apps-SU\$Architecture"
        Write-Log "Local Root: $script:LocalRoot"
        Write-Log "Local Apps Root: $script:LocalAppsRoot"

        # Set AppsRoot based on Location parameter
        if ($Location -eq 'OneDrive' -and $script:OneDriveAppsRoot) {
            $script:AppsRoot = $script:OneDriveAppsRoot
            Write-Log "Installation target: OneDrive ($script:AppsRoot)"
        } else {
            $script:AppsRoot = $script:LocalAppsRoot
            Write-Log "Installation target: Local ($script:AppsRoot)"
        }

        # Create Apps-SU directories if they don't exist
        if ($script:OneDriveAppsRoot -and -not (Test-Path -LiteralPath $script:OneDriveAppsRoot)) {
            New-Item -Path $script:OneDriveAppsRoot -ItemType Directory -Force | Out-Null
        }
        if (-not (Test-Path -LiteralPath $script:LocalAppsRoot)) {
            New-Item -Path $script:LocalAppsRoot -ItemType Directory -Force | Out-Null
        }
        $script:LocalGitRoot = Join-Path $script:LocalAppsRoot "Git"
        if (-not (Test-Path -LiteralPath $script:LocalGitRoot)) {
            New-Item -Path $script:LocalGitRoot -ItemType Directory -Force | Out-Null
        }

        # Create temp folder
        $script:TempDownloadFolder = Join-Path $env:TEMP "DevToolsInstaller_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        New-Item -Path $script:TempDownloadFolder -ItemType Directory -Force | Out-Null
        Write-Log "Temp folder: $script:TempDownloadFolder"
    }

    #endregion Initialize-Environment
    #region Test-ToolInstalled

    function Test-ToolInstalled {
        [CmdletBinding()]
        [OutputType([PSCustomObject])]
        param(
            [Parameter(Mandatory = $true)]
            [ValidateSet("Node", "Git", "ClaudeCode", "Python", "VSCode", "GitHubDesktop", "PowerShell7")]
            [string]$ToolName
        )

        $config = $script:ToolConfigs[$ToolName]

        function Test-LocationStatus {
            param(
                [string]$BasePath,
                [string[]]$ExecutablesToCheck,
                [bool]$IsClaudeCode = $false
            )

            $locationStatus = [PSCustomObject]@{
                BasePath = $BasePath
                FolderExists = $false
                ExecutablesFound = $false
                ExecutableDetails = @()
                InEnvironmentPath = $false
                MissingExecutables = @()
            }

            if ($IsClaudeCode) {
                $locationStatus | Add-Member -NotePropertyName 'GitBashPathSet' -NotePropertyValue $false
                $locationStatus | Add-Member -NotePropertyName 'GitBashPathValid' -NotePropertyValue $false
                $locationStatus | Add-Member -NotePropertyName 'GitBashPath' -NotePropertyValue ""
            }

            $locationStatus.FolderExists = Test-Path -LiteralPath $BasePath

            if (-not $locationStatus.FolderExists) {
                return $locationStatus
            }

            # Check executables
            $allExist = $true
            $missingExes = @()
            $exeDetails = @()

            foreach ($executable in $ExecutablesToCheck) {
                $exePath = Join-Path $BasePath $executable
                $exists = Test-Path -LiteralPath $exePath

                $exeDetails += [PSCustomObject]@{
                    Name = $executable
                    FullPath = $exePath
                    Found = $exists
                }

                if (-not $exists) {
                    $allExist = $false
                    $missingExes += $executable
                }
            }

            $locationStatus.ExecutablesFound = $allExist
            $locationStatus.ExecutableDetails = $exeDetails
            $locationStatus.MissingExecutables = $missingExes

            # Check PATH - look for any of the required paths
            $pathDirs = $env:Path -split ';' | ForEach-Object { $_.TrimEnd('\') }

            # For tools with PathSubfolder, check if that's in PATH
            if ($config.PathSubfolder) {
                $expectedPath = Join-Path $BasePath $config.PathSubfolder
                $locationStatus.InEnvironmentPath = $pathDirs -contains $expectedPath.TrimEnd('\')
            } else {
                $locationStatus.InEnvironmentPath = $pathDirs -contains $BasePath.TrimEnd('\')
            }

            # Special check for ClaudeCode
            if ($IsClaudeCode) {
                $gitBashPath = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")
                if (-not $gitBashPath) { $gitBashPath = $env:CLAUDE_CODE_GIT_BASH_PATH }

                $locationStatus.GitBashPathSet = -not [string]::IsNullOrEmpty($gitBashPath)
                $locationStatus.GitBashPath = $gitBashPath

                if ($locationStatus.GitBashPathSet) {
                    $locationStatus.GitBashPathValid = Test-Path -LiteralPath $gitBashPath
                }
            }

            return $locationStatus
        }

        # Determine paths
        $oneDrivePath = ""
        $localPath = ""
        $isClaudeCode = $false

        if ($ToolName -eq 'ClaudeCode') {
            # Claude Code is always in user profile
            $userProfilePath = Join-Path $env:USERPROFILE ".local\bin"
            $oneDrivePath = ""
            $localPath = $userProfilePath
            $isClaudeCode = $true
        } elseif ($ToolName -eq 'GitHubDesktop') {
            # GitHub Desktop always installs to LocalAppData via official installer
            $oneDrivePath = ""
            $localPath = Join-Path $env:LOCALAPPDATA "GitHubDesktop"
        } elseif ($ToolName -eq 'PowerShell7') {
            # PowerShell 7 is installed via winget; check for pwsh.exe on PATH
            $oneDrivePath = ""
            $pwshCmd = Get-Command pwsh.exe -ErrorAction SilentlyContinue
            if ($pwshCmd) {
                $localPath = Split-Path $pwshCmd.Source -Parent
            } else {
                # Check common Microsoft Store install location
                $localPath = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
            }
        } else {
            if ($script:OneDriveAppsRoot) {
                $oneDrivePath = Join-Path $script:OneDriveAppsRoot $config.FolderName
            }
            if ($script:LocalAppsRoot) {
                $localPath = Join-Path $script:LocalAppsRoot $config.FolderName
            }
        }

        # Check both locations
        $oneDriveStatus = if ($oneDrivePath) {
            Test-LocationStatus -BasePath $oneDrivePath -ExecutablesToCheck $config.ExecutablesToCheck -IsClaudeCode $isClaudeCode
        } else {
            [PSCustomObject]@{
                BasePath = "N/A"
                FolderExists = $false
                ExecutablesFound = $false
                ExecutableDetails = @()
                InEnvironmentPath = $false
                MissingExecutables = $config.ExecutablesToCheck
            }
        }

        $localStatus = if ($localPath) {
            Test-LocationStatus -BasePath $localPath -ExecutablesToCheck $config.ExecutablesToCheck -IsClaudeCode $isClaudeCode
        } else {
            [PSCustomObject]@{
                BasePath = "N/A"
                FolderExists = $false
                ExecutablesFound = $false
                ExecutableDetails = @()
                InEnvironmentPath = $false
                MissingExecutables = $config.ExecutablesToCheck
            }
        }

        return [PSCustomObject]@{
            ProgramName = $ToolName
            OneDrive = $oneDriveStatus
            Local = $localStatus
            IsInstalledAnywhere = ($oneDriveStatus.ExecutablesFound -or $localStatus.ExecutablesFound)
            IsInstalledBothLocations = ($oneDriveStatus.ExecutablesFound -and $localStatus.ExecutablesFound)
        }
    }

    #endregion Test-ToolInstalled
    #region Test-VSCodeSystemInstalled

    function Test-VSCodeSystemInstalled {
        [CmdletBinding()]
        [OutputType([PSCustomObject])]
        param()

        $result = [PSCustomObject]@{
            IsInstalled = $false
            InstallPath = $null
            InEnvironmentPath = $false
        }

        # Common VS Code installation patterns in PATH
        $vsCodePathPatterns = @(
            '*Microsoft VS Code*',
            '*VSCode*'
        )

        $pathDirs = $env:Path -split ';' | Where-Object { $_ }

        foreach ($dir in $pathDirs) {
            foreach ($pattern in $vsCodePathPatterns) {
                if ($dir -like $pattern) {
                    # Verify code.cmd exists
                    $codeCmdPath = Join-Path $dir "code.cmd"
                    if (Test-Path -LiteralPath $codeCmdPath) {
                        $result.IsInstalled = $true
                        $result.InstallPath = $dir
                        $result.InEnvironmentPath = $true
                        return $result
                    }
                }
            }
        }

        return $result
    }

    #endregion Test-VSCodeSystemInstalled
    #region Test-PythonSystemInstalled

    function Test-PythonSystemInstalled {
        [CmdletBinding()]
        [OutputType([PSCustomObject])]
        param()

        $result = [PSCustomObject]@{
            IsInstalled = $false
            InstallPath = $null
            InEnvironmentPath = $false
        }

        # Check if python is available via Get-Command (catches Microsoft Store and other system installs)
        try {
            $pythonCmd = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($pythonCmd) {
                # Exclude our own portable installations
                $pythonPath = $pythonCmd.Source
                if ($pythonPath -notlike "*Apps-SU*") {
                    $result.IsInstalled = $true
                    $result.InstallPath = Split-Path $pythonPath -Parent
                    $result.InEnvironmentPath = $true
                    return $result
                }
            }
        }
        catch {
            # Get-Command failed, continue with manual checks
        }

        # Fallback: Check common system installation paths
        $pathDirs = $env:Path -split ';' | Where-Object { $_ }

        $systemPythonPatterns = @(
            '*\Python\Python*',
            '*\Python3*'
        )

        foreach ($dir in $pathDirs) {
            # Skip our portable installation paths
            if ($dir -like "*Apps-SU*") { continue }

            foreach ($pattern in $systemPythonPatterns) {
                if ($dir -like $pattern) {
                    $pythonExePath = Join-Path $dir "python.exe"
                    if (Test-Path -LiteralPath $pythonExePath) {
                        $result.IsInstalled = $true
                        $result.InstallPath = $dir
                        $result.InEnvironmentPath = $true
                        return $result
                    }
                }
            }
        }

        return $result
    }

    #endregion Test-PythonSystemInstalled
    #region Show-InstallationStatus

    function Show-InstallationStatus {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [PSCustomObject]$Status
        )

        $config = $script:ToolConfigs[$Status.ProgramName]

        if ($Status.OneDrive.ExecutablesFound -and $Status.ProgramName -ne 'ClaudeCode' -and $Status.ProgramName -ne 'GitHubDesktop' -and $Status.ProgramName -ne 'PowerShell7') {
            Write-Log ">>> $($config.Name) is already installed in OneDrive <<<" -Level Success
            Write-Log "    Location: $($Status.OneDrive.BasePath)"
            Write-Log "    In PATH: $($Status.OneDrive.InEnvironmentPath)"
        }

        if ($Status.Local.ExecutablesFound) {
            Write-Log ">>> $($config.Name) is already installed Locally <<<" -Level Success
            Write-Log "    Location: $($Status.Local.BasePath)"
            Write-Log "    In PATH: $($Status.Local.InEnvironmentPath)"
            if ($Status.ProgramName -eq 'ClaudeCode') {
                Write-Log "    Git Bash Path Set: $($Status.Local.GitBashPathSet)"
                Write-Log "    Git Bash Path Valid: $($Status.Local.GitBashPathValid)"
            }
        }

        if ($Status.IsInstalledBothLocations) {
            Write-Log "WARNING: $($config.Name) is installed in BOTH locations - may cause conflicts!" -Level Warning
        }
    }

    #endregion Show-InstallationStatus
    #region Get-EnvironmentPath

    function Get-EnvironmentPath {
        [CmdletBinding()]
        param()

        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                    [Environment]::GetEnvironmentVariable("Path", "Machine")
        $env:CLAUDE_CODE_GIT_BASH_PATH = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")
        Write-Log "Environment PATH refreshed"
    }

    #endregion Get-EnvironmentPath
    #region Get-FileFromUrl

    function Get-FileFromUrl {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string]$Url,
            [Parameter(Mandatory = $true)]
            [string]$OutputPath
        )

        Write-Log "Downloading: $Url"

        $webClient = New-Object System.Net.WebClient

        if (-not $Quiet) {
            Register-ObjectEvent -InputObject $webClient -EventName DownloadProgressChanged -SourceIdentifier WebClient.DownloadProgressChanged -Action {
                Write-Progress -Activity "Downloading" -Status "$($EventArgs.ProgressPercentage)% Complete" -PercentComplete $EventArgs.ProgressPercentage
            } | Out-Null
        }

        try {
            $webClient.DownloadFile($Url, $OutputPath)
            if (-not (Test-Path -LiteralPath $OutputPath)) {
                throw "Download completed but file not found"
            }
        }
        finally {
            if (-not $Quiet) {
                Unregister-Event -SourceIdentifier WebClient.DownloadProgressChanged -ErrorAction SilentlyContinue
                Write-Progress -Activity "Downloading" -Completed
            }
            $webClient.Dispose()
        }
    }

    #endregion Get-FileFromUrl
    #region Expand-ArchiveFile

    function Expand-ArchiveFile {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string]$ArchivePath,
            [Parameter(Mandatory = $true)]
            [string]$DestinationPath
        )

        Write-Log "Extracting: $ArchivePath"

        if (-not (Test-Path -LiteralPath $DestinationPath)) {
            New-Item -Path $DestinationPath -ItemType Directory -Force | Out-Null
        }

        $extension = [System.IO.Path]::GetExtension($ArchivePath).ToLower()

        switch ($extension) {
            '.zip' {
                Expand-Archive -Path $ArchivePath -DestinationPath $DestinationPath -Force
            }
            '.exe' {
                $process = Start-Process -FilePath $ArchivePath -ArgumentList "-o`"$DestinationPath`" -y" -Wait -PassThru -NoNewWindow
                if ($process.ExitCode -ne 0) {
                    throw "Extraction failed with exit code: $($process.ExitCode)"
                }
            }
            default {
                throw "Unsupported archive format: $extension"
            }
        }
    }

    #endregion Expand-ArchiveFile
    #region Update-UserPath

    function Update-UserPath {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string[]]$Paths
        )

        if ($SkipPathUpdate) {
            Write-Log "Skipping PATH update (SkipPathUpdate flag set)"
            return
        }

        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if (-not $currentPath) { $currentPath = "" }

        $modified = $false
        foreach ($path in $Paths) {
            if (-not (Test-Path -LiteralPath $path)) {
                Write-Log "Path does not exist, skipping: $path" -Level Warning
                continue
            }

            $normalizedPath = $path.TrimEnd('\')
            $pathDirs = $currentPath -split ';' | ForEach-Object { $_.TrimEnd('\') }

            if ($pathDirs -notcontains $normalizedPath) {
                if ($currentPath) {
                    $currentPath = "$currentPath;$path"
                } else {
                    $currentPath = $path
                }
                $modified = $true
                Write-Log "Added to PATH: $path"
            } else {
                Write-Log "Already in PATH: $path"
            }
        }

        if ($modified) {
            [Environment]::SetEnvironmentVariable("Path", $currentPath, "User")
            Get-EnvironmentPath
            Write-Log "PATH updated successfully"
        }
    }

    #endregion Update-UserPath
    #region Set-ClaudeCodeRegistryEntry

    function Set-ClaudeCodeRegistryEntry {
        [CmdletBinding()]
        param($exePath)

        # Only set registry entry for ARM64
        if (-not (Get-CimInstance Win32_Processor | Select-Object Architecture).Architecture -contains 12) {
            return
        }

        Write-Log "Configuring app compatibility registry entry for Claude Code..."

        try {
            $regPath = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"

            # Check if the registry path exists
            if (-not (Test-Path -LiteralPath $regPath)) {
                Write-Log "Creating registry path: $regPath"
                New-Item -Path $regPath -Force | Out-Null
            }

            # Set the ARM64HIDEAVX value to allow x64 emulation on ARM64
            Write-Log "Setting ARM64HIDEAVX registry value..."
            # Create the key if it doesn't exist
            if (!(Test-Path $regPath)) {
                New-Item -Path $regPath -Force | Out-Null
            }

            # Set the compatibility flag
            # "~ ARM64HIDEAVX" is the flag for "Hide newer emulated CPU features"
            Set-ItemProperty -Path $regPath -Name $exePath -Value "~ ARM64HIDEAVX"

            Write-Log "Registry entry configured successfully"
        }
        catch {
            Write-Log "Warning: Failed to configure registry entry: $_" -Level Warning
            Write-Log "Installation may still proceed, but x64 compatibility may not be optimized" -Level Warning
        }
    }

    #endregion Set-ClaudeCodeRegistryEntry
    #region Install-ClaudeCodeOfficial

    function Install-ClaudeCodeOfficial {
        [CmdletBinding()]
        param()

        Write-Log "Installing Claude Code using official Anthropic installer..."

        # Verify Git is installed and CLAUDE_CODE_GIT_BASH_PATH is set
        $gitBashPath = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")
        if (-not $gitBashPath) {
            throw "CLAUDE_CODE_GIT_BASH_PATH not set. Git must be installed first."
        }

        if (-not (Test-Path -LiteralPath $gitBashPath)) {
            throw "CLAUDE_CODE_GIT_BASH_PATH points to invalid location: $gitBashPath"
        }

        Write-Log "Git Bash found at: $gitBashPath"

        # Refresh session PATH to ensure Git and other tools are available
        Get-EnvironmentPath

        Write-Log "Installing Claude Code..."
        try {
            # Execute Anthropic's official installation script in current session
            if ((Get-CimInstance Win32_Processor | Select-Object Architecture).Architecture -contains 12) {
                # ARM64-specific installation logic
                $GCS_BUCKET = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"
                $DOWNLOAD_DIR = "$env:USERPROFILE\.claude\downloads"
                $USERLOCAL_DIR = "$env:USERPROFILE\.local\bin"

                Write-Log "Installing Claude Code..."
                # Always use x64 for Windows (ARM64 Windows can run x64 through emulation)
                $platform = "win32-x64"
                New-Item -ItemType Directory -Force -Path $DOWNLOAD_DIR | Out-Null
                New-Item -ItemType Directory -Force -Path $USERLOCAL_DIR | Out-Null
                Update-UserPath(@("$USERLOCAL_DIR"))

                # Always download latest version (which has the most up-to-date installer)
                try {
                    Write-Log "Getting version..."
                    $version = Invoke-RestMethod -Uri "$GCS_BUCKET/latest" -ErrorAction Stop
                }
                catch {
                    throw "Failed to get latest version: $_"
                }

                try {
                    Write-Log "Getting manifest..."
                    $manifest = Invoke-RestMethod -Uri "$GCS_BUCKET/$version/manifest.json" -ErrorAction Stop
                    $checksum = $manifest.platforms.$platform.checksum

                    if (-not $checksum) {
                        throw "Platform $platform not found in manifest"
                    }
                }
                catch {
                    throw "Failed to get manifest: $_"
                }

                # Download and verify
                Write-Log "Downloading binary..."
                $binaryPath = "$DOWNLOAD_DIR\claude-$version-$platform.exe"
                try {
                    Invoke-WebRequest -Uri "$GCS_BUCKET/$version/$platform/claude.exe" -OutFile $binaryPath -ErrorAction Stop
                }
                catch {
                    throw "Failed to download binary: $_"
                    if (Test-Path $binaryPath) {
                        Remove-Item -Force $binaryPath
                    }
                }

                # Calculate checksum
                Write-Log "Verifying checksum..."
                $actualChecksum = (Get-FileHash -Path $binaryPath -Algorithm SHA256).Hash.ToLower()

                if ($actualChecksum -ne $checksum) {
                    throw "Checksum verification failed"
                    Remove-Item -Force $binaryPath
                }

                # Run claude install to set up launcher and shell integration
                Write-Output "Setting up Claude Code..."
                try {
                    & $binaryPath install "latest"
                }
                finally {
                    try {
                        # Clean up downloaded file
                        Start-Sleep -Seconds 1
                    }
                    catch {
                        Write-Warning "Could not remove temporary file: $binaryPath"
                    }
                }
                Write-Log "Claude Code installation completed"

                # Verify installation and move exe if needed
                $claudeExe = Join-Path $USERLOCAL_DIR "claude.exe"
                if (-not (Test-Path -LiteralPath $claudeExe)) {
                    if (Test-Path -LiteralPath "$DOWNLOAD_DIR\claude-$version-$platform.exe") {
                        Write-Log "Moving Claude Code exe from $DOWNLOAD_DIR\claude-$version-$platform.exe to $USERLOCAL_DIR\claude.exe"
                        try {
                            Move-Item -Path "$DOWNLOAD_DIR\claude-$version-$platform.exe" -Destination "$USERLOCAL_DIR\claude.exe"
                            Write-Log "Successfully moved and renamed Claude Code exe location."
                        }
                        catch { throw "Failed to move and rename Claude Code exe" }
                    }
                }
                # Configure registry entry for ARM64 compatibility
                Set-ClaudeCodeRegistryEntry -exePath "$USERLOCAL_DIR\claude.exe"
                Write-Log "Set Claude Code registry entry for ARM64 compatibility"
            } else {
                # x64-specific installation (simpler, uses official installer)
                $null = Invoke-Expression (Invoke-RestMethod -Uri 'https://claude.ai/install.ps1')
                Write-Log "Claude Code installation completed"
            }
        }
        catch {
            Write-Error "Claude Code installation failed: $_"
            throw
        }

        # Verify installation
        $claudeCodePath = Join-Path $env:USERPROFILE ".local\bin"
        $claudeExe = Join-Path $claudeCodePath "claude.exe"

        if (Test-Path -LiteralPath $claudeExe) {
            Write-Log "Claude Code executable found at: $claudeExe"

            # Ensure it's in PATH
            if (-not $SkipPathUpdate) {
                Update-UserPath -Paths @($claudeCodePath)
            }
        } else {
            throw "Claude Code installation completed but executable not found at: $claudeExe"
        }
    }

    #endregion Install-ClaudeCodeOfficial
    #region Install-GitHubDesktopOfficial

    function Install-GitHubDesktopOfficial {
        [CmdletBinding()]
        param()

        Write-Log "Installing GitHub Desktop using official installer..."

        $config = $script:ToolConfigs['GitHubDesktop']
        $installerPath = Join-Path $script:TempDownloadFolder "GitHubDesktopSetup.exe"

        Get-FileFromUrl -Url $config.DownloadUrl -OutputPath $installerPath

        Write-Log "Running GitHub Desktop installer silently..."
        $process = Start-Process -FilePath $installerPath -ArgumentList '--silent' -Wait -PassThru -NoNewWindow

        # Squirrel installers may return non-zero on success; treat as informational
        if ($process.ExitCode -ne 0) {
            Write-Log "Installer exited with code: $($process.ExitCode) (may be normal for Squirrel installers)" -Level Warning
        }

        # Wait up to 60 s for the exe to appear (Squirrel can finish async)
        $githubDesktopPath = Join-Path $env:LOCALAPPDATA "GitHubDesktop"
        $exePath = Join-Path $githubDesktopPath "GitHubDesktop.exe"
        $waited = 0
        while (-not (Test-Path -LiteralPath $exePath) -and $waited -lt 60) {
            Start-Sleep -Seconds 2
            $waited += 2
        }

        if (-not (Test-Path -LiteralPath $exePath)) {
            throw "GitHub Desktop installation completed but executable not found at: $exePath"
        }

        Write-Log "GitHub Desktop installed to: $githubDesktopPath"
    }

    #endregion Install-GitHubDesktopOfficial
    #region Install-PowerShell7Winget

    function Install-PowerShell7Winget {
        [CmdletBinding()]
        param()

        Write-Log "Installing PowerShell 7 via winget..."

        # Check if winget is available
        $wingetCmd = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $wingetCmd) {
            throw "winget is not available on this system. Please install App Installer from the Microsoft Store first."
        }

        # Check if PowerShell 7 is already installed
        $pwshCmd = Get-Command pwsh.exe -ErrorAction SilentlyContinue
        if ($pwshCmd) {
            Write-Log "PowerShell 7 is already installed at: $($pwshCmd.Source)"
            return
        }

        # Install from Microsoft Store via winget
        # The msstore source requires interactive agreement acceptance on first use.
        # Pipe "Y" via cmd to accept the Terms of Transaction and region consent prompts.
        Write-Log "Installing PowerShell 7 from Microsoft Store via winget..."
        try {
            $process = Start-Process -FilePath "cmd.exe" -ArgumentList '/c echo Y | winget install --id 9MZ1SNWT0N5D --source msstore --accept-package-agreements --accept-source-agreements --silent' -Wait -PassThru -NoNewWindow
            if ($process.ExitCode -ne 0) {
                # winget may return non-zero for "already installed" or "needs reboot"
                Write-Log "winget exited with code: $($process.ExitCode)" -Level Warning
            }
        }
        catch {
            Write-Error "PowerShell 7 installation failed: $_"
            throw
        }

        # Verify installation
        # Refresh PATH to pick up newly installed pwsh
        Get-EnvironmentPath

        $pwshCmd = Get-Command pwsh.exe -ErrorAction SilentlyContinue
        if ($pwshCmd) {
            Write-Log "PowerShell 7 installed successfully: $($pwshCmd.Source)"
        } else {
            Write-Log "PowerShell 7 installation completed. You may need to restart your terminal for pwsh to be available on PATH." -Level Warning
        }
    }

    #endregion Install-PowerShell7Winget
    #region Install-Tool

    function Install-Tool {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory = $true)]
            [string]$ToolName
        )

        Write-Host $ToolName
        $config = $script:ToolConfigs[$ToolName]
        if (-not $config) {
            throw "Tool configuration not found: $ToolName"
        }

        # Special check for VS Code - see if system-installed version exists
        if ($ToolName -eq 'VSCode') {
            $systemVSCode = Test-VSCodeSystemInstalled
            if ($systemVSCode.IsInstalled) {
                if($systemVSCode.InstallPath -like "*OneDrive*")
                {
                    Write-Log ">>> VS Code is already installed in OneDrive <<<" -Level Success
                } else 
                {
                    Write-Log ">>> VS Code is already installed on the system <<<" -Level Success
                }
                Write-Log "    Location: $($systemVSCode.InstallPath)"
                Write-Log "    Skipping portable installation"
                return
            }
        }

        # Special check for Python - see if Microsoft Store version exists
        if ($ToolName -eq 'Python') {
            $systemPython = Test-PythonSystemInstalled
            if ($systemPython.IsInstalled) {
                Write-Log ">>> Python is already installed on the system (Microsoft Store) <<<" -Level Success
                Write-Log "    Location: $($systemPython.InstallPath)"
                Write-Log "    Skipping portable installation"
                return
            }
        }

        # Special check for PowerShell 7 - see if pwsh is already available
        if ($ToolName -eq 'PowerShell7') {
            $pwshCmd = Get-Command pwsh.exe -ErrorAction SilentlyContinue
            if ($pwshCmd) {
                Write-Log ">>> PowerShell 7 is already installed <<<" -Level Success
                Write-Log "    Location: $($pwshCmd.Source)"
                Write-Log "    Skipping installation"
                return
            }
        }

        # Check if already installed
        $status = Test-ToolInstalled -ToolName $ToolName

        if ($status.IsInstalledAnywhere) {
            Show-InstallationStatus -Status $status

            # Still update PATH if needed
            $needsPathUpdate = $false
            if ($Location -eq 'OneDrive' -and $status.OneDrive.ExecutablesFound -and -not $status.OneDrive.InEnvironmentPath) {
                $needsPathUpdate = $true
                $toolPath = $status.OneDrive.BasePath
            } elseif ($Location -eq 'Local' -and $status.Local.ExecutablesFound -and -not $status.Local.InEnvironmentPath) {
                $needsPathUpdate = $true
                $toolPath = $status.Local.BasePath
            } elseif ($ToolName -eq 'ClaudeCode' -and $status.Local.ExecutablesFound -and -not $status.Local.InEnvironmentPath) {
                $needsPathUpdate = $true
                $toolPath = $status.Local.BasePath
            }

            if ($needsPathUpdate) {
                Write-Log "Updating PATH for already installed $($config.Name)..."
                $pathsToAdd = @()
                if ($config.PathSubfolder) {
                    $pathsToAdd += Join-Path $toolPath $config.PathSubfolder
                } else {
                    $pathsToAdd += $toolPath
                }

                if ($config.AdditionalPaths) {
                    foreach ($additionalPath in $config.AdditionalPaths) {
                        $pathsToAdd += Join-Path $toolPath $additionalPath
                    }
                }

                Update-UserPath -Paths $pathsToAdd
            }

            return  # Skip installation
        }

        # Not installed - proceed with installation
        Write-Log "`nInstalling $($config.Name)..."

        # Determine installation path
        if ($ToolName -eq 'ClaudeCode') {
            # Claude Code uses official installer
            Install-ClaudeCodeOfficial
            return
        } elseif ($ToolName -eq 'GitHubDesktop') {
            # GitHub Desktop uses official Squirrel installer
            Install-GitHubDesktopOfficial
            return
        } elseif ($ToolName -eq 'PowerShell7') {
            # PowerShell 7 installed via winget
            Install-PowerShell7Winget
            return
        } else {
            $toolPath = Join-Path $script:AppsRoot $config.FolderName
        }

        # Download
        $uri = [System.Uri]$config.DownloadUrl
        $fileName = [System.IO.Path]::GetFileName($uri.LocalPath)
        if ([string]::IsNullOrWhiteSpace($fileName) -or [string]::IsNullOrWhiteSpace([System.IO.Path]::GetExtension($fileName))) {
            $fileName = "$($config.FolderName)-download.zip"
        }

        $downloadPath = Join-Path $script:TempDownloadFolder $fileName
        Get-FileFromUrl -Url $config.DownloadUrl -OutputPath $downloadPath

        # Extract
        if ($config.FlattenArchive) {
            if ($ToolName -eq 'VSCode') {
                $extractedFolder = Join-Path $script:TempDownloadFolder "$($config.FolderName)_extract"
                Expand-ArchiveFile -ArchivePath $downloadPath -DestinationPath $extractedFolder

                if (Test-Path -LiteralPath $toolPath) {
                    Remove-Item -Path $toolPath -Recurse -Force
                }
                Move-Item -Path $extractedFolder -Destination $toolPath -Force
            } else {
                $tempExtractPath = Join-Path $script:TempDownloadFolder "$($config.FolderName)_extract"
                Expand-ArchiveFile -ArchivePath $downloadPath -DestinationPath $tempExtractPath

                $extractedFolder = Get-ChildItem -Path $tempExtractPath -Directory | Select-Object -First 1
                if (-not $extractedFolder) {
                    throw "Extraction did not produce expected folder structure"
                }

                if (Test-Path -LiteralPath $toolPath) {
                    Remove-Item -Path $toolPath -Recurse -Force
                }
                Move-Item -Path $extractedFolder.FullName -Destination $toolPath -Force
            }
        } else {
            if (Test-Path -LiteralPath $toolPath) {
                Remove-Item -Path $toolPath -Recurse -Force
            }
            Expand-ArchiveFile -ArchivePath $downloadPath -DestinationPath $toolPath
        }

        Write-Log "Installed to: $toolPath"

        # Post-install script
        if ($config.PostInstallScript) {
            Write-Log "Running post-install configuration..."
            & $config.PostInstallScript $toolPath
        }

        # Update PATH
        $pathsToAdd = @()
        if ($config.PathSubfolder) {
            $pathsToAdd += Join-Path $toolPath $config.PathSubfolder
        } else {
            $pathsToAdd += $toolPath
        }

        if ($config.AdditionalPaths) {
            foreach ($additionalPath in $config.AdditionalPaths) {
                $fullPath = Join-Path $toolPath $additionalPath
                # Only add if it's a directory (not a file like bash.exe)
                if (Test-Path -LiteralPath $fullPath -PathType Container) {
                    $pathsToAdd += $fullPath
                }
            }
        }

        Update-UserPath -Paths $pathsToAdd
        Write-Log "$($config.Name) installation complete"
    }

    #endregion Install-Tool
    #region Remove-DownloadedFiles

    function Remove-DownloadedFiles {
        [CmdletBinding()]
        param()

        if ($script:TempDownloadFolder -and (Test-Path -LiteralPath $script:TempDownloadFolder)) {
            Remove-Item -Path $script:TempDownloadFolder -Recurse -Force -ErrorAction SilentlyContinue
            Write-Log "Cleaned up temporary files"
        }
    }

    #endregion Remove-DownloadedFiles
}

#region Main Process

process {
    try {
        Write-Log "=== Development Tools Installer ==="
        Write-Log "Installation Location: $Location"
        Write-Host ""

        Initialize-Environment

        # Determine which tools to install
        $toolsToInstall = if ($Tools -contains 'All') {
            @('Node', 'Git', 'Python', 'VSCode', 'ClaudeCode', 'GitHubDesktop', 'PowerShell7')  # Specific order: Git before ClaudeCode
        } else {
            # Ensure Git comes before ClaudeCode if both are requested
            $orderedTools = @()
            if ($Tools -contains 'Git') { $orderedTools += 'Git' }
            foreach ($tool in $Tools) {
                if ($tool -ne 'Git' -and $tool -ne 'ClaudeCode' -and $tool -ne 'GitHubDesktop' -and $tool -ne 'PowerShell7') {
                    $orderedTools += $tool
                }
            }
            if ($Tools -contains 'ClaudeCode') {
                if($Tools -notcontains 'Git') # if claudecode is requested but not Git, add Git as well (prereq)
                { $orderedTools += 'Git' }
                $orderedTools += 'ClaudeCode'
            }
            if ($Tools -contains 'GitHubDesktop') { $orderedTools += 'GitHubDesktop' }
            if ($Tools -contains 'PowerShell7') { $orderedTools += 'PowerShell7' }
            $orderedTools
        }

        Write-Log "Tools to process: $($toolsToInstall -join ', ')"
        Write-Host ""

        # Install each tool
        foreach ($tool in $toolsToInstall) {
            try {
                # Special check for ClaudeCode - ensure Git is installed first
                if ($tool -eq 'ClaudeCode') {
                    $gitStatus = Test-ToolInstalled -ToolName 'Git'
                    if (-not $gitStatus.IsInstalledAnywhere) {
                        Write-Log "WARNING: ClaudeCode requires Git to be installed first. Skipping ClaudeCode." -Level Warning
                        continue
                    }

                    # Verify CLAUDE_CODE_GIT_BASH_PATH is set
                    $gitBashPath = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")
                    if (-not $gitBashPath -or -not (Test-Path -LiteralPath $gitBashPath)) {
                        Write-Log "WARNING: CLAUDE_CODE_GIT_BASH_PATH not properly set. Skipping ClaudeCode." -Level Warning
                        Write-Log "Please run the script again after Git installation completes." -Level Warning
                        continue
                    }
                }

                Install-Tool -ToolName $tool
                Write-Host ""
            }
            catch {
                Write-Log "Failed to install $tool : $_" -Level Error
                Write-Log "Continuing with remaining tools..." -Level Warning
                Write-Host ""
            }
        }

        Write-Log "=== Installation Summary ==="
        foreach ($tool in $toolsToInstall) {
            $status = Test-ToolInstalled -ToolName $tool
            $config = $script:ToolConfigs[$tool]

            if ($status.IsInstalledAnywhere) {
                Write-Log "[OK] $($config.Name) - Installed" -Level Success
            } else {
                # Special case for VSCode - check system installation too
                if ($tool -eq 'VSCode') {
                    $systemVSCode = Test-VSCodeSystemInstalled
                    if ($systemVSCode.IsInstalled) {
                        Write-Log "[OK] $($config.Name) - Installed (System)" -Level Success
                        continue
                    }
                }
                # Special case for Python - check Microsoft Store installation too
                if ($tool -eq 'Python') {
                    $systemPython = Test-PythonSystemInstalled
                    if ($systemPython.IsInstalled) {
                        Write-Log "[OK] $($config.Name) - Installed (Microsoft Store)" -Level Success
                        continue
                    }
                }
                # Special case for PowerShell7 - check if pwsh is on PATH
                if ($tool -eq 'PowerShell7') {
                    $pwshCmd = Get-Command pwsh.exe -ErrorAction SilentlyContinue
                    if ($pwshCmd) {
                        Write-Log "[OK] $($config.Name) - Installed" -Level Success
                        continue
                    }
                }
                Write-Log "[--] $($config.Name) - Not Installed" -Level Warning
            }
        }

        Write-Host ""
        Write-Log "=== Installation Complete ===" -Level Success
        Write-Log "IMPORTANT: Restart your terminal or PowerShell session to use the newly installed tools"
        Write-Host ""
    }
    catch {
        Write-Log "Installation failed: $_" -Level Error
        throw
    }
    finally {
        Remove-DownloadedFiles
    }
}

#endregion Main Process

end {}
