[CmdletBinding()]
param(
    [ValidateSet("All", "SkillsOnly", "GlobalOnly")]
    [string]$Component = "All",
    [switch]$NoBackup,
    [switch]$ForceReplaceGlobal
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
$BeginMarker = "<!-- codex-cross-project-assistant:begin -->"
$EndMarker = "<!-- codex-cross-project-assistant:end -->"

function Backup-Path {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$RelativeName
    )
    if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }
    $BackupPath = Join-Path $BackupRoot $RelativeName
    $BackupParent = Split-Path -Parent $BackupPath
    New-Item -ItemType Directory -Force -Path $BackupParent | Out-Null
    Copy-Item -LiteralPath $Path -Destination $BackupPath -Recurse -Force
    Write-Host "已备份: $Path -> $BackupPath"
}

function Install-Global {
    if (-not (Test-Path -LiteralPath $SourceGlobal)) {
        throw "缺少全局规则文件: $SourceGlobal"
    }

    New-Item -ItemType Directory -Force -Path $CodexHome | Out-Null
    $Target = Join-Path $CodexHome "AGENTS.md"
    Backup-Path -Path $Target -RelativeName "codex\AGENTS.md"

    $SourceContent = (Get-Content -LiteralPath $SourceGlobal -Raw).Trim()
    if ($SourceContent -notmatch [regex]::Escape($BeginMarker) -or
        $SourceContent -notmatch [regex]::Escape($EndMarker)) {
        throw "安装包中的 AGENTS.md 缺少受管标记，已停止安装。"
    }

    if ($ForceReplaceGlobal -or -not (Test-Path -LiteralPath $Target)) {
        Set-Content -LiteralPath $Target -Value ($SourceContent + "`r`n") -Encoding UTF8
        Write-Host "已安装全局规则（完整写入）: $Target"
        return
    }

    $Existing = Get-Content -LiteralPath $Target -Raw
    $HasBegin = $Existing.Contains($BeginMarker)
    $HasEnd = $Existing.Contains($EndMarker)

    if ($HasBegin -xor $HasEnd) {
        throw "现有 AGENTS.md 的受管标记不完整。为避免破坏现有规则，已停止安装: $Target"
    }

    if ($HasBegin -and $HasEnd) {
        $Pattern = "(?s)" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker)
        $Regex = [regex]::new($Pattern)
        $Evaluator = [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $SourceContent }
        $Merged = $Regex.Replace($Existing, $Evaluator, 1)
        Set-Content -LiteralPath $Target -Value ($Merged.TrimEnd() + "`r`n") -Encoding UTF8
        Write-Host "已更新 AGENTS.md 中的本包受管区块，其他规则保持不变: $Target"
    } else {
        $Prefix = $Existing.TrimEnd()
        $Merged = if ([string]::IsNullOrWhiteSpace($Prefix)) {
            $SourceContent + "`r`n"
        } else {
            $Prefix + "`r`n`r`n" + $SourceContent + "`r`n"
        }
        Set-Content -LiteralPath $Target -Value $Merged -Encoding UTF8
        Write-Host "已将本包规则追加到现有 AGENTS.md，原有规则保持不变: $Target"
    }
}

function Install-Skills {
    if (-not (Test-Path -LiteralPath $SourceSkills)) {
        throw "缺少 Skills 目录: $SourceSkills"
    }

    New-Item -ItemType Directory -Force -Path $SkillsHome | Out-Null
    Get-ChildItem -LiteralPath $SourceSkills -Directory | Sort-Object Name | ForEach-Object {
        $Target = Join-Path $SkillsHome $_.Name
        Backup-Path -Path $Target -RelativeName (Join-Path "skills" $_.Name)
        if (Test-Path -LiteralPath $Target) {
            Remove-Item -LiteralPath $Target -Recurse -Force
        }
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
Write-Host "安装完成。请在 Codex 中运行 /skills；如未刷新，请重启 Codex。"
Write-Host "全局规则目录: $CodexHome"
Write-Host "Skills 目录: $SkillsHome"
if (-not $NoBackup) { Write-Host "备份目录: $BackupRoot" }
