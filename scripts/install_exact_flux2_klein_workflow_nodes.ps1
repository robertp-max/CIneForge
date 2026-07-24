<# 
Guarded installer for the exact FLUX.2 / Klein ComfyUI workflow support set.

Default mode is dry-run. Nothing is cloned, downloaded, updated, started, stopped, or
written unless -Execute is supplied. This script intentionally lives in CineForge but
targets an explicit external ComfyUI root only.
#>

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [Parameter(Mandatory = $true)]
    [string]$WorkflowPath,

    [string]$PythonExe = "python",

    [switch]$Execute,

    [switch]$UpdateExistingCheckouts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExecuteRequested = [bool]$Execute
$MutationEnabled = $ExecuteRequested -and -not $WhatIfPreference

if ($WhatIfPreference -and $ExecuteRequested) {
    Write-Host "WHATIF: -Execute was supplied, but PowerShell -WhatIf is active. Continuing in dry-run mode."
}

$ReviewedAtUtc = "2026-07-23T00:00:00Z"
$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSCommandPath)))

function Resolve-CanonicalPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    return [System.IO.Path]::GetFullPath($expanded)
}

function Resolve-ExistingCanonicalPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet("Any", "Container", "Leaf")][string]$PathType
    )

    $full = Resolve-CanonicalPath -Path $Path
    $item = Get-Item -LiteralPath $full -ErrorAction Stop
    if ($PathType -eq "Container" -and -not $item.PSIsContainer) {
        throw "Expected a directory path: $full"
    }
    if ($PathType -eq "Leaf" -and $item.PSIsContainer) {
        throw "Expected a file path: $full"
    }

    return $item.FullName
}

function Assert-UnderPath {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $childFull = Resolve-CanonicalPath -Path $Child
    $parentFull = (Resolve-CanonicalPath -Path $Parent).TrimEnd('\') + '\'
    if (-not $childFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label path is outside expected parent: $childFull"
    }
}

function Assert-OutsidePath {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $childFull = Resolve-CanonicalPath -Path $Child
    $parentFull = (Resolve-CanonicalPath -Path $Parent).TrimEnd('\') + '\'
    if ($childFull.StartsWith($parentFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label must not be inside the CineForge repository: $childFull"
    }
}

function Assert-ComfyUIRoot {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "ComfyUI root does not exist: $Root"
    }

    $markers = @(
        @{ RelativePath = "main.py"; PathType = "Leaf" },
        @{ RelativePath = "custom_nodes"; PathType = "Container" },
        @{ RelativePath = "models"; PathType = "Container" },
        @{ RelativePath = "user"; PathType = "Container" }
    )

    foreach ($marker in $markers) {
        $markerPath = Join-Path -Path $Root -ChildPath $marker.RelativePath
        if (-not (Test-Path -LiteralPath $markerPath -PathType $marker.PathType)) {
            throw "ComfyUI marker missing or wrong type: $markerPath"
        }
    }
}

function Assert-ReviewedGitHubUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string[]]$AllowedUrls
    )

    $uri = [Uri]$Url
    if ($uri.Scheme -ne "https") {
        throw "Only HTTPS URLs are allowed: $Url"
    }
    if ($uri.Host -ne "github.com") {
        throw "Only github.com custom-node repositories are allowed: $Url"
    }
    if ($Url -notin $AllowedUrls) {
        throw "URL is not in the reviewed allowlist: $Url"
    }
    if ($Url -match "@|token|apikey|api_key|password|secret") {
        throw "URL appears to contain a credential-like value and is refused."
    }
}

function Assert-ReviewedDownloadUrl {
    param([Parameter(Mandatory = $true)][string]$Url)

    $uri = [Uri]$Url
    $allowed = "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors"
    if ($uri.Scheme -ne "https" -or $uri.Host -ne "huggingface.co" -or $Url -ne $allowed) {
        throw "Download URL is not the reviewed FLUX.2 VAE URL: $Url"
    }
    if ($Url -match "@|token|apikey|api_key|password|secret") {
        throw "Download URL appears to contain a credential-like value and is refused."
    }
}

function Assert-CommitSha {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    if ($Commit -notmatch "^[0-9a-f]{40}$") {
        throw "$Name is not pinned to a full 40-character commit SHA."
    }
}

function ConvertTo-SafeLogText {
    param([AllowNull()][string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    $safe = $Text -replace "(?i)(https?://)([^/\s:@]+):([^@\s/]+)@", '$1***:***@'
    $safe = $safe -replace "(?i)(token|apikey|api_key|password|secret)=([^&\s]+)", '$1=***'
    return $safe.Trim()
}

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $FilePath
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    foreach ($argument in $ArgumentList) {
        [void]$processInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::Start($processInfo)
    if ($null -eq $process) {
        throw "$FailureMessage Process did not start."
    }

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        $safeStderr = ConvertTo-SafeLogText -Text $stderr
        throw "$FailureMessage Exit code: $($process.ExitCode). $safeStderr"
    }

    return [ordered]@{
        Stdout = ConvertTo-SafeLogText -Text $stdout
        Stderr = ConvertTo-SafeLogText -Text $stderr
    }
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ExistingCheckoutSafeForUpdate {
    param(
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$ExpectedUrl,
        [Parameter(Mandatory = $true)][string]$PackageName
    )

    $inside = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $Target, "rev-parse", "--is-inside-work-tree") -FailureMessage "Existing checkout is not a Git worktree for $PackageName.").Stdout.Trim()
    if ($inside -ne "true") {
        throw "Existing checkout is not a Git worktree for $PackageName."
    }

    $remoteUrl = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $Target, "remote", "get-url", "origin") -FailureMessage "Could not read origin URL for $PackageName.").Stdout.Trim()
    if ($remoteUrl -ne $ExpectedUrl) {
        throw "Existing checkout origin URL does not match the reviewed allowlist for $PackageName."
    }
    if ($remoteUrl -match "@|token|apikey|api_key|password|secret") {
        throw "Existing checkout origin URL appears to contain a credential-like value and is refused."
    }

    $status = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $Target, "status", "--porcelain") -FailureMessage "Could not inspect working tree status for $PackageName.").Stdout.Trim()
    if ($status.Length -gt 0) {
        throw "Existing checkout has local changes and will not be updated automatically: $Target"
    }

    $head = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $Target, "rev-parse", "HEAD") -FailureMessage "Could not read HEAD for $PackageName.").Stdout.Trim()
    return [ordered]@{
        CurrentHead = $head
        RemoteUrl = $remoteUrl
    }
}

function Assert-RequirementsFileSafe {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$PackageName
    )

    $content = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ($content -match "(?i)(https?://[^/\s]+:[^@\s]+@|token|apikey|api_key|password|secret)") {
        throw "Requirements file for $PackageName contains credential-like text and is refused."
    }
}

$ComfyRootPath = Resolve-ExistingCanonicalPath -Path $ComfyUIRoot -PathType "Container"
$WorkflowFullPath = Resolve-ExistingCanonicalPath -Path $WorkflowPath -PathType "Leaf"
$CustomNodesPath = Join-Path -Path $ComfyRootPath -ChildPath "custom_nodes"
$VaePath = Join-Path -Path $ComfyRootPath -ChildPath "models\vae\flux2-vae.safetensors"

Assert-ComfyUIRoot -Root $ComfyRootPath
Assert-OutsidePath -Child $ComfyRootPath -Parent $RepoRoot -Label "ComfyUI root"
Assert-UnderPath -Child $CustomNodesPath -Parent $ComfyRootPath -Label "custom_nodes"
Assert-UnderPath -Child $VaePath -Parent $ComfyRootPath -Label "VAE target"
Assert-UnderPath -Child $WorkflowFullPath -Parent $ComfyRootPath -Label "workflow"
Assert-OutsidePath -Child $WorkflowFullPath -Parent $RepoRoot -Label "workflow"

if ((Split-Path -Leaf $WorkflowFullPath) -ne "Flux 2D & Klein_9b ver 7.0.json") {
    throw "Unexpected workflow file. Expected: Flux 2D & Klein_9b ver 7.0.json"
}

$Packages = @(
    @{
        Name = "ComfyUI-Flux2Klein-Enhancer"
        Directory = "ComfyUI-Flux2Klein-Enhancer"
        Url = "https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer.git"
        Commit = "6804643bff9a20926106427ff08d5b1bd2e49861"
    },
    @{
        Name = "rgthree-comfy"
        Directory = "rgthree-comfy"
        Url = "https://github.com/rgthree/rgthree-comfy.git"
        Commit = "27b4f4cdcf3b127c29d5d8135ac1536ecbd4c383"
    },
    @{
        Name = "ComfyUI-GGUF"
        Directory = "ComfyUI-GGUF"
        Url = "https://github.com/city96/ComfyUI-GGUF.git"
        Commit = "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"
    },
    @{
        Name = "ComfyUI-Custom-Scripts"
        Directory = "ComfyUI-Custom-Scripts"
        Url = "https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git"
        Commit = "609f3afaa74b2f88ef9ce8d939626065e3247469"
    },
    @{
        Name = "comfyui_controlnet_aux"
        Directory = "comfyui_controlnet_aux"
        Url = "https://github.com/Fannovel16/comfyui_controlnet_aux.git"
        Commit = "055e2442e4b3a6c8d71baf02f48b934acaf6fe61"
    },
    @{
        Name = "ComfyUI-Crystools"
        Directory = "ComfyUI-Crystools"
        Url = "https://github.com/crystian/ComfyUI-Crystools.git"
        Commit = "2f18256c5b5063937106f29a8e0a7db3ae3869b7"
    },
    @{
        Name = "ComfyUI-Impact-Pack"
        Directory = "ComfyUI-Impact-Pack"
        Url = "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git"
        Commit = "429d0159ad429e64d2b3916e6e7be9c22d025c3c"
    },
    @{
        Name = "ComfyUI-Impact-Subpack"
        Directory = "ComfyUI-Impact-Subpack"
        Url = "https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git"
        Commit = "d63cdfb3f99571b7681107456645e61a194b47f3"
    },
    @{
        Name = "ComfyUI_JPS-Nodes"
        Directory = "ComfyUI_JPS-Nodes"
        Url = "https://github.com/JPS-GER/ComfyUI_JPS-Nodes.git"
        Commit = "0e2a9aca02b17dde91577bfe4b65861df622dcaf"
    },
    @{
        Name = "ComfyUI_LayerStyle"
        Directory = "ComfyUI_LayerStyle"
        Url = "https://github.com/chflame163/ComfyUI_LayerStyle.git"
        Commit = "3d4a3526a9d1a19671a133e9215077bda520ee5d"
    }
)

$Vae = @{
    FileName = "flux2-vae.safetensors"
    Url = "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors"
    Sha256 = "d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5"
    TargetPath = $VaePath
}

$AllowedUrls = $Packages | ForEach-Object { $_.Url }
foreach ($package in $Packages) {
    Assert-ReviewedGitHubUrl -Url $package.Url -AllowedUrls $AllowedUrls
    Assert-CommitSha -Name $package.Name -Commit $package.Commit
}
Assert-ReviewedDownloadUrl -Url $Vae.Url
if ($Vae.Sha256 -notmatch "^[0-9a-f]{64}$") {
    throw "VAE SHA-256 is not a full 64-character lowercase hash."
}
if ((Split-Path -Leaf $Vae.TargetPath) -ne $Vae.FileName) {
    throw "VAE target filename does not match the reviewed FLUX.2 VAE filename."
}

$Actions = New-Object System.Collections.Generic.List[object]
$Rollback = New-Object System.Collections.Generic.List[object]

foreach ($package in $Packages) {
    $target = Join-Path -Path $CustomNodesPath -ChildPath $package.Directory
    Assert-UnderPath -Child $target -Parent $CustomNodesPath -Label $package.Name
    $requirements = Join-Path -Path $target -ChildPath "requirements.txt"

    if (Test-Path -LiteralPath $target -PathType Container) {
        if (-not $UpdateExistingCheckouts) {
            $Actions.Add([ordered]@{
                target = $target
                package = $package.Name
                action = "preserve_existing_checkout"
                reason = "UpdateExistingCheckouts was not supplied."
            })
            continue
        }

        $checkoutState = Assert-ExistingCheckoutSafeForUpdate -Target $target -ExpectedUrl $package.Url -PackageName $package.Name

        $Actions.Add([ordered]@{
            target = $target
            package = $package.Name
            action = $(if ($MutationEnabled) { "update_existing_checkout" } else { "would_update_existing_checkout" })
            previousHead = $checkoutState.CurrentHead
            commit = $package.Commit
        })

        if ($MutationEnabled) {
            if (-not $PSCmdlet.ShouldProcess($target, "Update existing checkout to reviewed commit $($package.Commit)")) {
                throw "PowerShell ShouldProcess declined update for $($package.Name)."
            }
            Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $target, "fetch", "origin", $package.Commit, "--depth", "1") -FailureMessage "Git fetch failed for $($package.Name)."
            Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $target, "checkout", "--detach", $package.Commit) -FailureMessage "Git checkout failed for $($package.Name)."
            $actual = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $target, "rev-parse", "HEAD") -FailureMessage "Git HEAD verification failed for $($package.Name).").Stdout.Trim()
            if ($actual -ne $package.Commit) {
                throw "Pinned commit verification failed for $($package.Name). Expected $($package.Commit), got $actual."
            }
        }

        $Rollback.Add([ordered]@{
            package = $package.Name
            installedPath = $target
            previousHead = $checkoutState.CurrentHead
            rollback = "Manual review required before checking out the previous commit."
        })
    }
    else {
        $installing = Join-Path -Path $CustomNodesPath -ChildPath (".installing-" + $package.Directory + "-" + $package.Commit)
        Assert-UnderPath -Child $installing -Parent $CustomNodesPath -Label "$($package.Name) temporary checkout"
        if (Test-Path -LiteralPath $installing) {
            throw "Temporary install path already exists: $installing"
        }

        $Actions.Add([ordered]@{
            target = $target
            package = $package.Name
            action = $(if ($MutationEnabled) { "clone_pinned_checkout" } else { "would_clone_pinned_checkout" })
            commit = $package.Commit
            temporaryPath = $installing
        })

        if ($MutationEnabled) {
            if (-not $PSCmdlet.ShouldProcess($target, "Clone reviewed repository and check out pinned commit $($package.Commit)")) {
                throw "PowerShell ShouldProcess declined clone for $($package.Name)."
            }
            Invoke-CheckedProcess -FilePath "git" -ArgumentList @("clone", "--no-checkout", $package.Url, $installing) -FailureMessage "Git clone failed for $($package.Name)."
            Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $installing, "fetch", "origin", $package.Commit, "--depth", "1") -FailureMessage "Git fetch failed for $($package.Name)."
            Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $installing, "checkout", "--detach", $package.Commit) -FailureMessage "Git checkout failed for $($package.Name)."
            $actual = (Invoke-CheckedProcess -FilePath "git" -ArgumentList @("-C", $installing, "rev-parse", "HEAD") -FailureMessage "Git HEAD verification failed for $($package.Name).").Stdout.Trim()
            if ($actual -ne $package.Commit) {
                throw "Pinned commit verification failed for $($package.Name). Expected $($package.Commit), got $actual."
            }
            [System.IO.Directory]::Move($installing, $target)
        }

        $Rollback.Add([ordered]@{
            package = $package.Name
            installedPath = $target
            rollback = "Manual review required before removing this checkout."
        })
    }

    if (Test-Path -LiteralPath $requirements -PathType Leaf) {
        Assert-RequirementsFileSafe -Path $requirements -PackageName $package.Name
        $Actions.Add([ordered]@{
            target = $requirements
            package = $package.Name
            action = $(if ($MutationEnabled) { "install_requirements" } else { "would_install_requirements" })
            python = $PythonExe
        })

        if ($MutationEnabled) {
            if (-not $PSCmdlet.ShouldProcess($requirements, "Install Python dependencies for $($package.Name)")) {
                throw "PowerShell ShouldProcess declined dependency installation for $($package.Name)."
            }
            Invoke-CheckedProcess -FilePath $PythonExe -ArgumentList @("-m", "pip", "install", "-r", $requirements) -FailureMessage "Dependency install failed for $($package.Name)."
        }
    }
}

$vaeDir = Split-Path -Parent $Vae.TargetPath
Assert-UnderPath -Child $vaeDir -Parent $ComfyRootPath -Label "VAE directory"

if (Test-Path -LiteralPath $Vae.TargetPath -PathType Leaf) {
    $existingHash = Get-FileSha256 -Path $Vae.TargetPath
    if ($existingHash -ne $Vae.Sha256) {
        throw "Existing VAE hash mismatch at $($Vae.TargetPath). Expected $($Vae.Sha256), got $existingHash."
    }
    $Actions.Add([ordered]@{
        target = $Vae.TargetPath
        action = "preserve_existing_verified_vae"
        sha256 = $existingHash
    })
}
else {
    $tempVae = Join-Path -Path $vaeDir -ChildPath ($Vae.FileName + ".download")
    Assert-UnderPath -Child $tempVae -Parent $vaeDir -Label "VAE temporary file"
    $Actions.Add([ordered]@{
        target = $Vae.TargetPath
        temporaryPath = $tempVae
        action = $(if ($MutationEnabled) { "download_verify_and_move_vae" } else { "would_download_verify_and_move_vae" })
        sha256 = $Vae.Sha256
    })

    if ($MutationEnabled) {
        if (-not $PSCmdlet.ShouldProcess($Vae.TargetPath, "Download, hash-verify, and atomically place reviewed FLUX.2 VAE")) {
            throw "PowerShell ShouldProcess declined VAE placement."
        }
        if (-not (Test-Path -LiteralPath $vaeDir -PathType Container)) {
            New-Item -ItemType Directory -Path $vaeDir | Out-Null
        }
        if (Test-Path -LiteralPath $tempVae) {
            throw "Temporary VAE download already exists: $tempVae"
        }
        Invoke-WebRequest -Uri $Vae.Url -OutFile $tempVae -UseBasicParsing
        $downloadedHash = Get-FileSha256 -Path $tempVae
        if ($downloadedHash -ne $Vae.Sha256) {
            throw "Downloaded VAE hash mismatch. Expected $($Vae.Sha256), got $downloadedHash. Temporary file left for inspection: $tempVae"
        }
        [System.IO.File]::Move($tempVae, $Vae.TargetPath)
    }

    $Rollback.Add([ordered]@{
        file = $Vae.TargetPath
        rollback = "Manual review required before removing this verified VAE file."
    })
}

$Summary = [ordered]@{
    script = "install_exact_flux2_klein_workflow_nodes.ps1"
    reviewedAtUtc = $ReviewedAtUtc
    mode = $(if ($MutationEnabled) { "execute" } else { "dry_run" })
    executeSwitchPresent = $ExecuteRequested
    mutationEnabled = $MutationEnabled
    updateExistingCheckouts = [bool]$UpdateExistingCheckouts
    comfyUIRoot = $ComfyRootPath
    cineForgeRepoRoot = $RepoRoot
    workflowPath = $WorkflowFullPath
    customNodePackages = $Packages
    vae = $Vae
    actions = $Actions
    rollbackManifest = $Rollback
    guarantees = @(
        "No ComfyUI process is started or stopped.",
        "No CineForge source file is modified by this installer.",
        "No model binary is written inside the CineForge repository.",
        "Existing custom-node checkouts are preserved unless -UpdateExistingCheckouts and -Execute are both supplied.",
        "All executable custom-node packages are pinned to full reviewed commit SHAs.",
        "The FLUX.2 VAE is verified by SHA-256 before placement."
    )
}

if ($MutationEnabled) {
    $manifestPath = Join-Path -Path $CustomNodesPath -ChildPath ("cineforge_exact_workflow_install_manifest_" + (Get-Date -Format "yyyyMMddHHmmss") + ".json")
    $Summary.manifestPath = $manifestPath
    if (-not $PSCmdlet.ShouldProcess($manifestPath, "Write rollback manifest")) {
        throw "PowerShell ShouldProcess declined rollback manifest write."
    }
    ($Summary | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

$Summary | ConvertTo-Json -Depth 8
