[CmdletBinding()]
param(
    [string]$Repository = "C:\AI\Git\CIneForge",
    [string]$SourceRef = "feature/storyboard-phase-a-complete",
    [string]$CorpusWorktree = "C:\AI\Git\_worktrees\CIneForge-chatgpt-corpus",
    [switch]$Push
)

$ErrorActionPreference = "Stop"
$branch = "chatgpt/corpus"
$repoRoot = (git -C $Repository rev-parse --show-toplevel).Trim()
if ([IO.Path]::GetFullPath($repoRoot) -ne [IO.Path]::GetFullPath($Repository)) {
    throw "Repository top-level mismatch: $repoRoot"
}
$sourceSha = (git -C $Repository rev-parse "$SourceRef^{commit}").Trim()
$origin = (git -C $Repository remote get-url origin).Trim()
if (-not $origin) { throw "origin is not configured" }

if (-not (Test-Path -LiteralPath $CorpusWorktree)) {
    $remoteBranch = git -C $Repository show-ref --verify --quiet "refs/remotes/origin/$branch"
    if ($LASTEXITCODE -eq 0) {
        git -C $Repository worktree add --track -b $branch $CorpusWorktree "origin/$branch"
    } else {
        git -C $Repository worktree add -b $branch $CorpusWorktree $sourceSha
    }
}

$corpusRoot = (git -C $CorpusWorktree rev-parse --show-toplevel).Trim()
if ([IO.Path]::GetFullPath($corpusRoot) -ne [IO.Path]::GetFullPath($CorpusWorktree)) {
    throw "Corpus worktree top-level mismatch: $corpusRoot"
}
if ((git -C $CorpusWorktree branch --show-current).Trim() -ne $branch) {
    throw "Corpus worktree is not on $branch"
}
if (git -C $CorpusWorktree status --porcelain) {
    throw "Corpus worktree is not clean"
}

git -C $Repository fetch origin $branch --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
    $counts = (git -C $CorpusWorktree rev-list --left-right --count "origin/$branch...$branch").Trim() -split "\s+"
    if ([int]$counts[0] -gt 0) { throw "Corpus branch is behind or divergent; refusing to rewrite or force-push" }
}

$output = Join-Path $CorpusWorktree "docs\chatgpt-corpus"
$resolvedOutput = [IO.Path]::GetFullPath($output)
$resolvedRoot = [IO.Path]::GetFullPath($CorpusWorktree).TrimEnd('\') + '\'
if (-not $resolvedOutput.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Corpus output escaped its dedicated worktree"
}
if (Test-Path -LiteralPath $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}
New-Item -ItemType Directory -Path $resolvedOutput | Out-Null

$tracked = @(git -C $Repository ls-tree -r --name-only $sourceSha | Sort-Object)
$manifest = @(
    "# CineForge ChatGPT Corpus Index",
    "",
    "- Source ref: ``$SourceRef``",
    "- Source commit: ``$sourceSha``",
    "- Remote: ``$origin``",
    "- Generated UTC: ``$([DateTime]::UtcNow.ToString('O'))``",
    "",
    "## Tracked repository files",
    ""
) + ($tracked | ForEach-Object { "- ``$_``" })
Set-Content -LiteralPath (Join-Path $resolvedOutput "INDEX.md") -Value $manifest -Encoding utf8

$securityPattern = '(?i)(api[_-]?key\s*[:=]\s*\S+|bearer\s+[a-z0-9._-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
$finding = Get-ChildItem -LiteralPath $resolvedOutput -Recurse -File | Select-String -Pattern $securityPattern
if ($finding) { throw "Secret-like material found in generated corpus" }

git -C $CorpusWorktree add -- docs/chatgpt-corpus
git -C $CorpusWorktree diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Output "Corpus unchanged for $sourceSha"
    exit 0
}
git -C $CorpusWorktree commit -m "docs: refresh ChatGPT corpus for $($sourceSha.Substring(0, 12))"
if ($Push) {
    git -C $CorpusWorktree push origin $branch
}
