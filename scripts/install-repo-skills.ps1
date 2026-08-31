[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoPath,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path -LiteralPath $RepoPath).Path
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$SourceSkills = Join-Path $PackageRoot "skills"
$TargetSkills = Join-Path (Join-Path $Repo ".agents") "skills"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $Repo ".agents-backup-$Timestamp"

New-Item -ItemType Directory -Force -Path $TargetSkills | Out-Null
Get-ChildItem -LiteralPath $SourceSkills -Directory | ForEach-Object {
    $Target = Join-Path $TargetSkills $_.Name
    if ((Test-Path -LiteralPath $Target) -and -not $NoBackup) {
        New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
        Copy-Item -LiteralPath $Target -Destination (Join-Path $BackupRoot $_.Name) -Recurse -Force
    }
    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
    Write-Host "已安装仓库级 Skill: $($_.Name)"
}
Write-Host "仓库级 Skills 已安装到: $TargetSkills"
Write-Host "注意：该目录位于仓库内，是否提交到 Git 由你的项目规范决定。"
