[CmdletBinding()]
param(
    [ValidateSet("All", "SkillsOnly", "GlobalOnly", "ReviewAgentsOnly")]
    [string]$Component = "All",
    [switch]$NoBackup
)
$ErrorActionPreference = "Stop"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$AgentsHome = Join-Path $CodexHome "agents"
$BackupRoot = Join-Path (Join-Path $HOME ".codex-skill-backups") ("uninstall-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$BeginMarker = "<!-- codex-cross-project-assistant:begin -->"
$EndMarker = "<!-- codex-cross-project-assistant:end -->"
$ManagedSkills = @("java-backend-engineering", "python-backend-ai-engineering", "vue-frontend-engineering", "data-middleware-ai-infrastructure", "engineering-quality-delivery", "multi-agent-independent-review", "technical-document-writing", "long-running-task-memory")
$ManagedAgents = @("cp-review-functional-business.toml", "cp-review-compatibility-regression.toml", "cp-review-security-access.toml", "cp-review-performance-resources.toml", "cp-review-data-contract.toml", "cp-review-state-concurrency.toml", "cp-review-test-delivery.toml")

function Backup-Path { param([string]$Path, [string]$RelativeName); if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }; $Dest = Join-Path $BackupRoot $RelativeName; New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null; Copy-Item -LiteralPath $Path -Destination $Dest -Recurse -Force }
function Remove-GlobalBlock {
    $Target = Join-Path $CodexHome "AGENTS.md"; if (-not (Test-Path -LiteralPath $Target)) { Write-Host "未找到 AGENTS.md，跳过。"; return }
    Backup-Path -Path $Target -RelativeName "codex\AGENTS.md"; $Content = Get-Content -LiteralPath $Target -Raw
    $BeginCount = ([regex]::Matches($Content, [regex]::Escape($BeginMarker))).Count; $EndCount = ([regex]::Matches($Content, [regex]::Escape($EndMarker))).Count
    if ($BeginCount -ne $EndCount -or $BeginCount -gt 1) { throw "AGENTS.md 受管标记异常，停止卸载。" }
    if ($BeginCount -eq 0) { Write-Host "AGENTS.md 中没有本包受管区块，跳过。"; return }
    $Pattern = "(?s)\s*" + [regex]::Escape($BeginMarker) + ".*?" + [regex]::Escape($EndMarker) + "\s*"
    $Remaining = ([regex]::Replace($Content, $Pattern, "`r`n`r`n", 1)).Trim()
    if ([string]::IsNullOrWhiteSpace($Remaining)) { Remove-Item -LiteralPath $Target -Force; Write-Host "已删除仅包含本包规则的 AGENTS.md。" }
    else { Set-Content -LiteralPath $Target -Value ($Remaining + "`r`n") -Encoding UTF8; Write-Host "已移除本包 AGENTS.md 受管区块。" }
}
function Remove-Skills { foreach ($Name in $ManagedSkills) { $Target = Join-Path $SkillsHome $Name; if (Test-Path -LiteralPath $Target) { Backup-Path -Path $Target -RelativeName (Join-Path "skills" $Name); Remove-Item -LiteralPath $Target -Recurse -Force; Write-Host "已卸载 Skill: $Name" } } }
function Remove-ReviewAgents { foreach ($Name in $ManagedAgents) { $Target = Join-Path $AgentsHome $Name; if (Test-Path -LiteralPath $Target) { Backup-Path -Path $Target -RelativeName (Join-Path "agents" $Name); Remove-Item -LiteralPath $Target -Force; Write-Host "已卸载 Reviewer: $Name" } } }
switch ($Component) { "All" { Remove-GlobalBlock; Remove-Skills; Remove-ReviewAgents }; "SkillsOnly" { Remove-Skills }; "GlobalOnly" { Remove-GlobalBlock }; "ReviewAgentsOnly" { Remove-ReviewAgents } }
Write-Host "卸载完成。其他规则、Skills 和自定义 Agent 未被删除。"
if (-not $NoBackup) { Write-Host "备份目录: $BackupRoot" }
