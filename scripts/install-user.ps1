[CmdletBinding()]
param(
    [ValidateSet("All", "SkillsOnly", "GlobalOnly")]
    [string]$Component = "All",
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$SourceGlobal = Join-Path $PackageRoot "global\AGENTS.md"
$SourceSkills = Join-Path $PackageRoot "skills"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path (Join-Path $HOME ".codex-skill-backups") $Timestamp

function Backup-Path {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$RelativeName)
    if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }
    $BackupPath = Join-Path $BackupRoot $RelativeName
    $BackupParent = Split-Path -Parent $BackupPath
    New-Item -ItemType Directory -Force -Path $BackupParent | Out-Null
    Copy-Item -LiteralPath $Path -Destination $BackupPath -Recurse -Force
    Write-Host "已备份: $Path -> $BackupPath"
}

function Install-Global {
    if (-not (Test-Path -LiteralPath $SourceGlobal)) { throw "缺少全局规则文件: $SourceGlobal" }
    New-Item -ItemType Directory -Force -Path $CodexHome | Out-Null
    $Target = Join-Path $CodexHome "AGENTS.md"
    Backup-Path -Path $Target -RelativeName "codex\AGENTS.md"
    Copy-Item -LiteralPath $SourceGlobal -Destination $Target -Force
    Write-Host "已安装全局规则: $Target"
}

function Install-Skills {
    if (-not (Test-Path -LiteralPath $SourceSkills)) { throw "缺少 Skills 目录: $SourceSkills" }
    New-Item -ItemType Directory -Force -Path $SkillsHome | Out-Null
    Get-ChildItem -LiteralPath $SourceSkills -Directory | ForEach-Object {
        $Target = Join-Path $SkillsHome $_.Name
        Backup-Path -Path $Target -RelativeName (Join-Path "skills" $_.Name)
        if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
        Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
        Write-Host "已安装 Skill: $($_.Name)"
    }
}

switch ($Component) {
    "All" { Install-Global; Install-Skills }
    "SkillsOnly" { Install-Skills }
    "GlobalOnly" { Install-Global }
}

Write-Host ""
Write-Host "安装完成。Codex 中运行 /skills 检查技能；如未显示，请重启 Codex。"
Write-Host "全局规则目录: $CodexHome"
Write-Host "Skills 目录: $SkillsHome"
if (-not $NoBackup) { Write-Host "备份目录: $BackupRoot" }
