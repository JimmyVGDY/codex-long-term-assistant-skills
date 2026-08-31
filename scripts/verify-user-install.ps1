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
    "long-running-task-memory"
)

$Failed = $false
$AgentsFile = Join-Path $CodexHome "AGENTS.md"
if (Test-Path -LiteralPath $AgentsFile) {
    Write-Host "[OK] 全局 AGENTS.md: $AgentsFile"
} else {
    Write-Host "[缺失] 全局 AGENTS.md: $AgentsFile"
    $Failed = $true
}

foreach ($Name in $ExpectedSkills) {
    $SkillFile = Join-Path (Join-Path $SkillsHome $Name) "SKILL.md"
    if (-not (Test-Path -LiteralPath $SkillFile)) {
        Write-Host "[缺失] $SkillFile"
        $Failed = $true
        continue
    }
    $Content = Get-Content -LiteralPath $SkillFile -Raw
    if ($Content -notmatch "(?m)^name:\s+$([regex]::Escape($Name))\s*$" -or $Content -notmatch "(?m)^description:") {
        Write-Host "[格式错误] $SkillFile"
        $Failed = $true
    } else {
        Write-Host "[OK] Skill: $Name"
    }
}

if ($Failed) {
    Write-Host "验证失败。请检查上面的缺失或格式错误项。"
    exit 1
}

Write-Host "验证通过。请在 Codex 中运行 /skills；如列表未刷新，请重启 Codex。"
