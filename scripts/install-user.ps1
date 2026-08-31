[CmdletBinding()]
param(
    [ValidateSet("All", "SkillsOnly", "GlobalOnly", "ReviewAgentsOnly")]
    [string]$Component = "All",
    [switch]$ForceReplaceGlobal,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptDir
$SourceGlobal = Join-Path $PackageRoot "global\AGENTS.md"
$SourceSkills = Join-Path $PackageRoot "skills"
$SourceAgents = Join-Path $PackageRoot "custom-agents"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$AgentsHome = Join-Path $CodexHome "agents"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path (Join-Path $HOME ".codex-skill-backups") $Timestamp
$BeginMarker = "<!-- codex-cross-project-assistant:begin -->"
$EndMarker = "<!-- codex-cross-project-assistant:end -->"

function Backup-Path {
    param([string]$Path, [string]$RelativeName)
    if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }
    $Destination = Join-Path $BackupRoot $RelativeName
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $Path -Destination $Destination -Recurse -Force
    Write-Host "已备份: $Path -> $Destination"
}

function Install-Global {
    if (-not (Test-Path -LiteralPath $SourceGlobal)) { throw "缺少全局规则: $SourceGlobal" }
    $ManagedBlock = Get-Content -LiteralPath $SourceGlobal -Raw
    if (-not $ManagedBlock.Contains($BeginMarker) -or -not $ManagedBlock.Contains($EndMarker)) {
        throw "安装包全局规则缺少受管标记"
    }
    New-Item -ItemType Directory -Force -Path $CodexHome | Out-Null
    $Target = Join-Path $CodexHome "AGENTS.md"
    Backup-Path -Path $Target -RelativeName "codex\AGENTS.md"
    if ($ForceReplaceGlobal -or -not (Test-Path -LiteralPath $Target)) {
        Set-Content -LiteralPath $Target -Value $ManagedBlock -Encoding UTF8
        Write-Host "已安装全局规则（完整写入）: $Target"
        return
    }
    $Existing = Get-Content -LiteralPath $Target -Raw
    $BeginCount = ([regex]::Matches($Existing, [regex]::Escape($BeginMarker))).Count
    $EndCount = ([regex]::Matches($Existing, [regex]::Escape($EndMarker))).Count
    if ($BeginCount -ne $EndCount -or $BeginCount -gt 1) {
        throw "现有 AGENTS.md 的受管标记不完整或重复，已停止安装: $Target"
    }
    if ($BeginCount -eq 0) {
        $Merged = $Existing.TrimEnd() + "`r`n`r`n" + $ManagedBlock.Trim() + "`r`n"
    } else {
        $Pattern = "(?s)" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker)
        $Merged = [regex]::Replace($Existing, $Pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $ManagedBlock.Trim() }, 1)
    }
    Set-Content -LiteralPath $Target -Value $Merged -Encoding UTF8
    Write-Host "已更新 AGENTS.md 的本包受管区块，其他规则保持不变: $Target"
}

function Install-Skills {
    if (-not (Test-Path -LiteralPath $SourceSkills)) { throw "缺少 Skills 目录: $SourceSkills" }
    New-Item -ItemType Directory -Force -Path $SkillsHome | Out-Null
    Get-ChildItem -LiteralPath $SourceSkills -Directory | Sort-Object Name | ForEach-Object {
        $Target = Join-Path $SkillsHome $_.Name
        Backup-Path -Path $Target -RelativeName (Join-Path "skills" $_.Name)
        if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
        Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
        Write-Host "已安装 Skill: $($_.Name)"
    }
}

function Install-ReviewAgents {
    if (-not (Test-Path -LiteralPath $SourceAgents)) { throw "缺少自定义 Reviewer 目录: $SourceAgents" }
    New-Item -ItemType Directory -Force -Path $AgentsHome | Out-Null
    Get-ChildItem -LiteralPath $SourceAgents -File -Filter "*.toml" | Sort-Object Name | ForEach-Object {
        $Target = Join-Path $AgentsHome $_.Name
        Backup-Path -Path $Target -RelativeName (Join-Path "agents" $_.Name)
        Copy-Item -LiteralPath $_.FullName -Destination $Target -Force
        Write-Host "已安装只读 Reviewer: $($_.Name)"
    }
}

switch ($Component) {
    "All" { Install-Global; Install-Skills; Install-ReviewAgents }
    "SkillsOnly" { Install-Skills }
    "GlobalOnly" { Install-Global }
    "ReviewAgentsOnly" { Install-ReviewAgents }
}

Write-Host ""
Write-Host "安装完成。Skills 可用 /skills 查看；自定义 Reviewer 由主 Agent 在复审时调用。"
Write-Host "全局规则目录: $CodexHome"
Write-Host "Skills 目录: $SkillsHome"
Write-Host "Reviewer 目录: $AgentsHome"
Write-Host "安装脚本未修改 config.toml；可参考 config\agents.example.toml。"
if (-not $NoBackup) { Write-Host "备份目录: $BackupRoot" }
