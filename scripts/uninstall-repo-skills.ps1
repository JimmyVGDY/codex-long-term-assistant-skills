[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path -LiteralPath $RepoPath).Path
$TargetSkills = Join-Path (Join-Path $Repo ".agents") "skills"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $Repo (".agents-backup-uninstall-" + $Timestamp)
$ManagedSkills = @(
    "java-backend-engineering",
    "python-backend-ai-engineering",
    "vue-frontend-engineering",
    "data-middleware-ai-infrastructure",
    "engineering-quality-delivery",
    "technical-document-writing",
    "long-running-task-memory"
)
foreach ($Name in $ManagedSkills) {
    $Target = Join-Path $TargetSkills $Name
    if (Test-Path -LiteralPath $Target) {
        if (-not $NoBackup) {
            New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
            Copy-Item -LiteralPath $Target -Destination (Join-Path $BackupRoot $Name) -Recurse -Force
        }
        Remove-Item -LiteralPath $Target -Recurse -Force
        Write-Host "已卸载仓库级 Skill: $Name"
    }
}
Write-Host "仓库级卸载完成，其他 Skills 未被删除。"
