[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$SkillsHome = Join-Path (Join-Path $HOME ".agents") "skills"
$ExpectedSkills = @(
    "java-backend-engineering",
    "python-backend-ai-engineering",
    "vue-frontend-engineering",
    "data-middleware-ai-infrastructure",
    "engineering-quality-delivery",
    "technical-document-writing",
    "long-running-task-memory"
)
$RequiredDocumentTemplates = @(
    "TECHNICAL_SOLUTION.template.md",
    "ARCHITECTURE_DESIGN.template.md",
    "IMPLEMENTATION_PLAN.template.md",
    "API_DESIGN.template.md",
    "DATABASE_DESIGN.template.md",
    "DEPLOYMENT_RUNBOOK.template.md",
    "INCIDENT_REPORT.template.md",
    "CODE_REVIEW_REPORT.template.md",
    "PROJECT_PROGRESS_REPORT.template.md",
    "TECHNICAL_SELECTION.template.md",
    "README.template.md",
    "MANAGEMENT_REPORT.template.md"
)

$Failed = $false
$AgentsFile = Join-Path $CodexHome "AGENTS.md"
if (Test-Path -LiteralPath $AgentsFile) {
    $AgentsContent = Get-Content -LiteralPath $AgentsFile -Raw
    if ($AgentsContent -match [regex]::Escape("<!-- codex-cross-project-assistant:begin -->") -and
        $AgentsContent -match [regex]::Escape("<!-- codex-cross-project-assistant:end -->")) {
        Write-Host "[OK] 全局 AGENTS.md 受管区块: $AgentsFile"
    } else {
        Write-Host "[格式错误] AGENTS.md 存在，但缺少本包受管区块: $AgentsFile"
        $Failed = $true
    }
} else {
    Write-Host "[缺失] 全局 AGENTS.md: $AgentsFile"
    $Failed = $true
}

foreach ($Name in $ExpectedSkills) {
    $SkillDir = Join-Path $SkillsHome $Name
    $SkillFile = Join-Path $SkillDir "SKILL.md"
    $OpenAiFile = Join-Path (Join-Path $SkillDir "agents") "openai.yaml"
    if (-not (Test-Path -LiteralPath $SkillFile)) {
        Write-Host "[缺失] $SkillFile"
        $Failed = $true
        continue
    }
    $Content = Get-Content -LiteralPath $SkillFile -Raw
    if ($Content -notmatch "(?m)^name:\s+$([regex]::Escape($Name))\s*$" -or $Content -notmatch "(?m)^description:") {
        Write-Host "[格式错误] $SkillFile"
        $Failed = $true
    } elseif (-not (Test-Path -LiteralPath $OpenAiFile)) {
        Write-Host "[缺失] $OpenAiFile"
        $Failed = $true
    } else {
        Write-Host "[OK] Skill: $Name"
    }
}

$DocumentTemplatesDir = Join-Path (Join-Path (Join-Path $SkillsHome "technical-document-writing") "assets") "templates"
foreach ($Template in $RequiredDocumentTemplates) {
    $TemplatePath = Join-Path $DocumentTemplatesDir $Template
    if (-not (Test-Path -LiteralPath $TemplatePath)) {
        Write-Host "[缺失] 文档模板: $TemplatePath"
        $Failed = $true
    }
}
if (-not $Failed) {
    Write-Host "[OK] 技术文档模板: $($RequiredDocumentTemplates.Count) 个"
}

if ($Failed) {
    Write-Host "验证失败。请检查上面的缺失或格式错误项。"
    exit 1
}

Write-Host "验证通过。请在 Codex 中运行 /skills；如列表未刷新，请重启 Codex。"
