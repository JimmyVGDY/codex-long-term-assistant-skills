[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$AgentsHome = Join-Path $CodexHome "agents"
$Failed = $false
$ExpectedSkills = @(
    "java-backend-engineering", "python-backend-ai-engineering", "vue-frontend-engineering",
    "data-middleware-ai-infrastructure", "engineering-quality-delivery",
    "multi-agent-independent-review", "technical-document-writing", "long-running-task-memory"
)
$ExpectedAgents = @(
    "cp-review-functional-business.toml", "cp-review-compatibility-regression.toml",
    "cp-review-security-access.toml", "cp-review-performance-resources.toml",
    "cp-review-data-contract.toml", "cp-review-state-concurrency.toml",
    "cp-review-test-delivery.toml"
)
$DocTemplates = @(
    "TECHNICAL_SOLUTION.template.md", "ARCHITECTURE_DESIGN.template.md", "IMPLEMENTATION_PLAN.template.md",
    "API_DESIGN.template.md", "DATABASE_DESIGN.template.md", "DEPLOYMENT_RUNBOOK.template.md",
    "INCIDENT_REPORT.template.md", "CODE_REVIEW_REPORT.template.md", "PROJECT_PROGRESS_REPORT.template.md",
    "TECHNICAL_SELECTION.template.md", "README.template.md", "MANAGEMENT_REPORT.template.md"
)
$MemoryTemplates = @(
    "PROJECT_CONTEXT.template.md", "CURRENT_TASK.template.md", "PLAN.template.md", "PROGRESS.template.md",
    "DECISIONS.template.md", "HANDOFF.template.md", "KNOWN_ISSUES.template.md", "DELIVERY_RECORD.template.md",
    "CHECKPOINT_ENTRY.template.md", "RECOVERY_CHECKLIST.template.md"
)
$ReviewTemplates = @("REVIEW_PLAN.template.md", "REVIEW_RESULT.template.md", "REVIEW_LEDGER.template.md")

$GlobalFile = Join-Path $CodexHome "AGENTS.md"
if (Test-Path -LiteralPath $GlobalFile) {
    $Content = Get-Content -LiteralPath $GlobalFile -Raw
    if ($Content.Contains("<!-- codex-cross-project-assistant:begin -->") -and $Content.Contains("<!-- codex-cross-project-assistant:end -->")) {
        Write-Host "[OK] 全局 AGENTS.md 受管区块: $GlobalFile"
    } else { Write-Host "[缺失或格式错误] $GlobalFile"; $Failed = $true }
} else { Write-Host "[缺失] $GlobalFile"; $Failed = $true }

foreach ($Name in $ExpectedSkills) {
    $Dir = Join-Path $SkillsHome $Name
    $Skill = Join-Path $Dir "SKILL.md"
    $Metadata = Join-Path $Dir "agents\openai.yaml"
    if (-not (Test-Path -LiteralPath $Skill)) { Write-Host "[缺失] $Skill"; $Failed = $true; continue }
    $Text = Get-Content -LiteralPath $Skill -Raw
    if ($Text -notmatch "(?m)^name:\s*$([regex]::Escape($Name))\s*$" -or $Text -notmatch "(?m)^description:") {
        Write-Host "[格式错误] $Skill"; $Failed = $true
    } elseif (-not (Test-Path -LiteralPath $Metadata)) {
        Write-Host "[缺失] $Metadata"; $Failed = $true
    } else { Write-Host "[OK] Skill: $Name" }
}

foreach ($File in $ExpectedAgents) {
    $Path = Join-Path $AgentsHome $File
    if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[缺失] Reviewer: $Path"; $Failed = $true; continue }
    $Text = Get-Content -LiteralPath $Path -Raw
    if ($Text -notmatch "(?m)^name\s*=" -or $Text -notmatch "(?m)^description\s*=" -or
        $Text -notmatch "(?m)^developer_instructions\s*=" -or $Text -notmatch '(?m)^sandbox_mode\s*=\s*"read-only"') {
        Write-Host "[格式错误] Reviewer: $Path"; $Failed = $true
    } else { Write-Host "[OK] Reviewer: $File" }
}

function Test-Templates {
    param([string]$Directory, [string[]]$Names)
    foreach ($Name in $Names) {
        $Path = Join-Path $Directory $Name
        if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[缺失] 模板: $Path"; $script:Failed = $true }
    }
}
Test-Templates -Directory (Join-Path $SkillsHome "technical-document-writing\assets\templates") -Names $DocTemplates
Test-Templates -Directory (Join-Path $SkillsHome "long-running-task-memory\assets\templates") -Names $MemoryTemplates
Test-Templates -Directory (Join-Path $SkillsHome "multi-agent-independent-review\assets\templates") -Names $ReviewTemplates

$Checkpoint = Join-Path $SkillsHome "long-running-task-memory\scripts\checkpoint.py"
if (Test-Path -LiteralPath $Checkpoint) { Write-Host "[OK] 持续检查点辅助脚本" } else { Write-Host "[缺失] $Checkpoint"; $Failed = $true }

if ($Failed) { throw "验证失败。" }
Write-Host "[OK] Skills: $($ExpectedSkills.Count) 个"
Write-Host "[OK] 只读 Reviewer: $($ExpectedAgents.Count) 个"
Write-Host "[OK] 模板: 文档 $($DocTemplates.Count) / 记忆 $($MemoryTemplates.Count) / 复审 $($ReviewTemplates.Count)"
Write-Host "验证通过。请在 Codex 中运行 /skills；新增内容未刷新时重启 Codex。"
