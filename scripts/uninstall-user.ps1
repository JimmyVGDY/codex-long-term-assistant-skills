[CmdletBinding()]
param(
    [ValidateSet("All", "SkillsOnly", "GlobalOnly")]
    [string]$Component = "All",
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path (Join-Path $HOME ".codex-skill-backups") ("uninstall-" + $Timestamp)
$BeginMarker = "<!-- codex-cross-project-assistant:begin -->"
$EndMarker = "<!-- codex-cross-project-assistant:end -->"
$ManagedSkills = @(
    "java-backend-engineering",
    "python-backend-ai-engineering",
    "vue-frontend-engineering",
    "data-middleware-ai-infrastructure",
    "engineering-quality-delivery",
    "technical-document-writing",
    "long-running-task-memory"
)

function Backup-Path {
    param([string]$Path, [string]$RelativeName)
    if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }
    $BackupPath = Join-Path $BackupRoot $RelativeName
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BackupPath) | Out-Null
    Copy-Item -LiteralPath $Path -Destination $BackupPath -Recurse -Force
}

function Remove-GlobalBlock {
    $Target = Join-Path $CodexHome "AGENTS.md"
    if (-not (Test-Path -LiteralPath $Target)) {
        Write-Host "未找到全局 AGENTS.md，跳过。"
        return
    }
    Backup-Path -Path $Target -RelativeName "codex\AGENTS.md"
    $Content = Get-Content -LiteralPath $Target -Raw
    $HasBegin = $Content.Contains($BeginMarker)
    $HasEnd = $Content.Contains($EndMarker)
    if ($HasBegin -xor $HasEnd) {
        throw "AGENTS.md 的受管标记不完整，已停止卸载以避免破坏文件: $Target"
    }
    if (-not $HasBegin) {
        Write-Host "AGENTS.md 中没有本包受管区块，跳过。"
        return
    }
    $Pattern = "(?s)\s*" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker) + "\s*"
    $Regex = [regex]::new($Pattern)
    $Remaining = $Regex.Replace($Content, "`r`n`r`n", 1).Trim()
    if ([string]::IsNullOrWhiteSpace($Remaining)) {
        Remove-Item -LiteralPath $Target -Force
        Write-Host "已删除仅包含本包规则的 AGENTS.md: $Target"
    } else {
        Set-Content -LiteralPath $Target -Value ($Remaining + "`r`n") -Encoding UTF8
        Write-Host "已移除本包受管区块，其他全局规则保持不变: $Target"
    }
}

function Remove-Skills {
    foreach ($Name in $ManagedSkills) {
        $Target = Join-Path $SkillsHome $Name
        if (Test-Path -LiteralPath $Target) {
            Backup-Path -Path $Target -RelativeName (Join-Path "skills" $Name)
            Remove-Item -LiteralPath $Target -Recurse -Force
            Write-Host "已卸载 Skill: $Name"
        }
    }
}

switch ($Component) {
    "All" { Remove-GlobalBlock; Remove-Skills }
    "SkillsOnly" { Remove-Skills }
    "GlobalOnly" { Remove-GlobalBlock }
}

Write-Host "卸载完成。其他 Skills 和 AGENTS.md 中的非本包规则未被删除。"
if (-not $NoBackup) { Write-Host "备份目录: $BackupRoot" }
