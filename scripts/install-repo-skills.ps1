[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [switch]$IncludeReviewAgents,
    [switch]$NoBackup
)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path -LiteralPath $RepoPath).Path
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$SourceSkills = Join-Path $Root "skills"
$SourceAgents = Join-Path $Root "custom-agents"
$TargetSkills = Join-Path (Join-Path $Repo ".agents") "skills"
$TargetAgents = Join-Path (Join-Path $Repo ".codex") "agents"
$BackupRoot = Join-Path $Repo (".codex-skills-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $TargetSkills | Out-Null
Get-ChildItem -LiteralPath $SourceSkills -Directory | Sort-Object Name | ForEach-Object { $Target = Join-Path $TargetSkills $_.Name; if ((Test-Path -LiteralPath $Target) -and -not $NoBackup) { New-Item -ItemType Directory -Force -Path (Join-Path $BackupRoot "skills") | Out-Null; Copy-Item -LiteralPath $Target -Destination (Join-Path (Join-Path $BackupRoot "skills") $_.Name) -Recurse -Force }; if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }; Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force; Write-Host "已安装仓库级 Skill: $($_.Name)" }
if ($IncludeReviewAgents) { New-Item -ItemType Directory -Force -Path $TargetAgents | Out-Null; Get-ChildItem -LiteralPath $SourceAgents -File -Filter "*.toml" | Sort-Object Name | ForEach-Object { $Target = Join-Path $TargetAgents $_.Name; if ((Test-Path -LiteralPath $Target) -and -not $NoBackup) { New-Item -ItemType Directory -Force -Path (Join-Path $BackupRoot "agents") | Out-Null; Copy-Item -LiteralPath $Target -Destination (Join-Path (Join-Path $BackupRoot "agents") $_.Name) -Force }; Copy-Item -LiteralPath $_.FullName -Destination $Target -Force; Write-Host "已安装仓库级 Reviewer: $($_.Name)" } }
Write-Host "Skills: $TargetSkills"
if ($IncludeReviewAgents) { Write-Host "Reviewers: $TargetAgents" }
Write-Host "这些目录位于仓库中，是否提交 Git 由项目规范决定。"
