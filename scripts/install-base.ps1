[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Assert-NoReparseAncestor {
    param([Parameter(Mandatory = $true)][string]$Path)
    $current = [System.IO.Path]::GetFullPath($Path)
    while ($true) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Managed path contains a symbolic-link or reparse-point ancestor: $current"
            }
        }
        $parent = [System.IO.Directory]::GetParent($current)
        if ($null -eq $parent) { break }
        $current = $parent.FullName
    }
}

$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$codexHome = if ($env:CODEX_HOME) { [System.IO.Path]::GetFullPath($env:CODEX_HOME) } else { Join-Path $env:USERPROFILE '.codex' }
$baseState = Join-Path $codexHome 'cp-assistant-base-state.json'
$marketRoot = Join-Path $env:USERPROFILE '.agents\plugins\cp-assistant-base-marketplace'
$marketManifest = Join-Path $marketRoot '.agents\plugins\marketplace.json'
$pluginRoot = Join-Path $marketRoot 'plugins\codex-cross-project-engineering-assistant'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-BaseState {
    param([Parameter(Mandatory = $true)][string]$Status)
    $null = New-Item -ItemType Directory -Path $codexHome -Force
    $state = @{
        schema_version = 1
        package = 'codex-cross-project-engineering-assistant'
        marketplace = 'cp-assistant-base'
        market_root = $marketRoot
        status = $Status
    }
    [System.IO.File]::WriteAllText($baseState, ($state | ConvertTo-Json -Depth 4), $utf8NoBom)
}

function Remove-PartialBaseInstall {
    Assert-NoReparseAncestor -Path $codexHome
    Assert-NoReparseAncestor -Path $marketRoot
    & codex plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base recovery could not remove Plugin registration: $LASTEXITCODE" }
    & codex plugin marketplace remove 'cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base recovery could not remove Marketplace registration: $LASTEXITCODE" }
    if (Test-Path -LiteralPath $marketRoot) {
        Remove-Item -LiteralPath $marketRoot -Recurse -Force
    }
    Remove-Item -LiteralPath $baseState -Force -ErrorAction SilentlyContinue
}

Assert-NoReparseAncestor -Path $packageRoot
Assert-NoReparseAncestor -Path $codexHome
Assert-NoReparseAncestor -Path $marketRoot
if (Test-Path -LiteralPath $baseState) {
    try { $existingState = Get-Content -LiteralPath $baseState -Raw | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'Base Plugin state is invalid; refusing to overwrite it.' }
    $recoverable = $existingState.schema_version -eq 1 -and
        $existingState.package -eq 'codex-cross-project-engineering-assistant' -and
        $existingState.marketplace -eq 'cp-assistant-base' -and
        $existingState.market_root -eq $marketRoot -and
        $existingState.status -in @('INSTALLING', 'RECOVERY_REQUIRED')
    if ($recoverable) {
        Remove-PartialBaseInstall
    } else {
        throw 'Base Plugin is already installed by this entry; run install-user.ps1 for enhancements.'
    }
}
if (Test-Path -LiteralPath (Join-Path $codexHome 'cp-assistant-v6-state.json')) {
    throw 'A managed enhancement installation exists; refusing a base downgrade. Run install-user.ps1.'
}
if (Test-Path -LiteralPath $marketRoot) {
    throw "Base Marketplace directory exists: $marketRoot. Refusing to overwrite unknown files."
}

try {
    Write-BaseState -Status 'INSTALLING'
    New-Item -ItemType Directory -Path $pluginRoot -Force | Out-Null
    foreach ($name in @('.codex-plugin', 'skills', 'hooks')) {
        Copy-Item -LiteralPath (Join-Path $packageRoot $name) -Destination $pluginRoot -Recurse -Force
    }
    $manifest = @{
        name = 'cp-assistant-base'
        interface = @{ displayName = 'Codex Cross Project Assistant' }
        plugins = @(@{
            name = 'codex-cross-project-engineering-assistant'
            source = @{ source = 'local'; path = './plugins/codex-cross-project-engineering-assistant' }
            policy = @{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
            category = 'Productivity'
        })
    }
    $manifestDirectory = Split-Path -Parent $marketManifest
    New-Item -ItemType Directory -Path $manifestDirectory -Force | Out-Null
    [System.IO.File]::WriteAllText($marketManifest, ($manifest | ConvertTo-Json -Depth 8), $utf8NoBom)
    & codex plugin marketplace add $marketRoot
    if ($LASTEXITCODE -ne 0) { throw "Codex Marketplace registration failed: $LASTEXITCODE" }
    & codex plugin add 'codex-cross-project-engineering-assistant@cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base Plugin installation failed: $LASTEXITCODE" }
    & codex plugin list --json
    if ($LASTEXITCODE -ne 0) { throw "Base Plugin readback failed: $LASTEXITCODE" }
    Write-BaseState -Status 'INSTALLED'
} catch {
    $installError = $_
    try {
        Remove-PartialBaseInstall
    } catch {
        Write-BaseState -Status 'RECOVERY_REQUIRED'
        throw "Base installation failed and native cleanup is incomplete: $installError / $_"
    }
    throw $installError
}

Write-Output 'Base Plugin installed. Describe an engineering task directly; run install-user.ps1 for enhancements.'
