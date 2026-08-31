[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [switch]$IncludeReviewAgents,
    [switch]$NoBackup
)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path -LiteralPath $RepoPath).Path
$Skills = Join-Path (Join-Path $Repo ".agents") "skills"
$Agents = Join-Path (Join-Path $Repo ".codex") "agents"
$BackupRoot = Join-Path $Repo (".codex-skills-backup-uninstall-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$ManagedSkills = @("java-backend-engineering", "python-backend-ai-engineering", "vue-frontend-engineering", "data-middleware-ai-infrastructure", "engineering-quality-delivery", "multi-agent-independent-review", "technical-document-writing", "long-running-task-memory")
$ManagedAgents = @("cp-review-functional-business.toml", "cp-review-compatibility-regression.toml", "cp-review-security-access.toml", "cp-review-performance-resources.toml", "cp-review-data-contract.toml", "cp-review-state-concurrency.toml", "cp-review-test-delivery.toml")
foreach ($Name in $ManagedSkills) { $Target = Join-Path $Skills $Name; if (Test-Path -LiteralPath $Target) { if (-not $NoBackup) { New-Item -ItemType Directory -Force -Path (Join-Path $BackupRoot "skills") | Out-Null; Copy-Item -LiteralPath $Target -Destination (Join-Path (Join-Path $BackupRoot "skills") $Name) -Recurse -Force }; Remove-Item -LiteralPath $Target -Recurse -Force; Write-Host "已卸载仓库级 Skill: $Name" } }
if ($IncludeReviewAgents) { foreach ($Name in $ManagedAgents) { $Target = Join-Path $Agents $Name; if (Test-Path -LiteralPath $Target) { if (-not $NoBackup) { New-Item -ItemType Directory -Force -Path (Join-Path $BackupRoot "agents") | Out-Null; Copy-Item -LiteralPath $Target -Destination (Join-Path (Join-Path $BackupRoot "agents") $Name) -Force }; Remove-Item -LiteralPath $Target -Force; Write-Host "已卸载仓库级 Reviewer: $Name" } } }
Write-Host "仓库级卸载完成，其他 Skills 和 Agent 未被删除。"
