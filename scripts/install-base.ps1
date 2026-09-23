[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Get-ExactFileSystemItem {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        return $item
    } catch {
        if ($_.CategoryInfo.Category -ne 'ObjectNotFound') {
            throw "Cannot safely inspect managed path: $Path / $($_.Exception.Message)"
        }
    }
    $parent = [System.IO.Directory]::GetParent($Path)
    if ($null -eq $parent) { return $null }
    try {
        $parentItem = Get-Item -LiteralPath $parent.FullName -Force -ErrorAction Stop
    } catch {
        if ($_.CategoryInfo.Category -eq 'ObjectNotFound') { return $null }
        throw "Cannot safely inspect managed path parent: $($parent.FullName) / $($_.Exception.Message)"
    }
    if (-not $parentItem.PSIsContainer) { return $null }
    $leaf = [System.IO.Path]::GetFileName($Path)
    try {
        $candidates = Get-ChildItem -LiteralPath $parent.FullName -Force -ErrorAction Stop
    } catch {
        if ($_.CategoryInfo.Category -eq 'ObjectNotFound') { return $null }
        throw "Cannot safely enumerate managed path parent: $($parent.FullName) / $($_.Exception.Message)"
    }
    foreach ($candidate in $candidates) {
        if ($candidate.Name -eq $leaf) { return $candidate }
    }
    return $null
}

function Assert-NoReparseAncestor {
    param([Parameter(Mandatory = $true)][string]$Path)
    $current = [System.IO.Path]::GetFullPath($Path)
    while ($true) {
        $item = Get-ExactFileSystemItem -Path $current
        if ($null -ne $item -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Managed path contains a symbolic-link or reparse-point ancestor: $current"
        }
        $parent = [System.IO.Directory]::GetParent($current)
        if ($null -eq $parent) { break }
        $current = $parent.FullName
    }
}

$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$codexHome = if ($env:CODEX_HOME) { [System.IO.Path]::GetFullPath($env:CODEX_HOME) } else { Join-Path $env:USERPROFILE '.codex' }
$desktopComponent = if ($env:CP_ASSISTANT_DESKTOP_COMPONENT) { [System.IO.Path]::GetFullPath($env:CP_ASSISTANT_DESKTOP_COMPONENT) } else { Join-Path $codexHome 'plugins\.plugin-appserver\codex.exe' }
$baseState = Join-Path $codexHome 'cp-assistant-base-state.json'
$enhancementState = Join-Path $codexHome 'cp-assistant-v6-state.json'
$marketRoot = Join-Path $env:USERPROFILE '.agents\plugins\cp-assistant-base-marketplace'
$marketManifest = Join-Path $marketRoot '.agents\plugins\marketplace.json'
$pluginRoot = Join-Path $marketRoot 'plugins\codex-cross-project-engineering-assistant'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-BaseState {
    param([Parameter(Mandatory = $true)][string]$Status)
    Assert-NoReparseAncestor -Path $baseState
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

function Copy-PayloadTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    Assert-NoReparseAncestor -Path $Destination
    $sourceItem = Get-Item -LiteralPath $Source -Force
    if (-not $sourceItem.PSIsContainer) {
        throw "Base Plugin payload source is not a directory: $Source"
    }
    $destinationItem = Get-ExactFileSystemItem -Path $Destination
    if ($null -ne $destinationItem -and -not $destinationItem.PSIsContainer) {
        throw "Base Plugin payload target is a file: $Destination"
    }
    [System.IO.Directory]::CreateDirectory($Destination) | Out-Null
    foreach ($item in ([System.IO.DirectoryInfo]$Source).GetFileSystemInfos()) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Base Plugin payload contains a link-like entry: $($item.FullName)"
        }
        $target = Join-Path $Destination $item.Name
        if ($item -is [System.IO.DirectoryInfo]) {
            Copy-PayloadTree -Source $item.FullName -Destination $target
        } else {
            [System.IO.File]::Copy($item.FullName, $target, $true)
        }
    }
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function New-BaseManifest {
    return [ordered]@{
        name = 'cp-assistant-base'
        interface = [ordered]@{ displayName = 'Codex Cross Project Assistant' }
        plugins = @([ordered]@{
            name = 'codex-cross-project-engineering-assistant'
            source = [ordered]@{ source = 'local'; path = './plugins/codex-cross-project-engineering-assistant' }
            policy = [ordered]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
            category = 'Productivity'
        })
    }
}

function Remove-PayloadTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    Assert-NoReparseAncestor -Path $Destination
    $destinationItem = Get-ExactFileSystemItem -Path $Destination
    if ($null -eq $destinationItem) { return }
    if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Base recovery found a link-like payload target: $Destination"
    }
    $sourceItem = Get-Item -LiteralPath $Source -Force
    if ($sourceItem -is [System.IO.DirectoryInfo]) {
        if (-not $destinationItem.PSIsContainer) {
            throw "Base recovery found a file where a payload directory is expected: $Destination"
        }
        foreach ($item in ([System.IO.DirectoryInfo]$Source).GetFileSystemInfos()) {
            Remove-PayloadTree -Source $item.FullName -Destination (Join-Path $Destination $item.Name)
        }
        if (@(Get-ChildItem -LiteralPath $Destination -Force).Count -eq 0) {
            Remove-Item -LiteralPath $Destination -Force
        }
        return
    }
    if ($destinationItem.PSIsContainer) {
        throw "Base recovery found a directory where a payload file is expected: $Destination"
    }
    if ((Get-FileSha256 -Path $Source) -ne (Get-FileSha256 -Path $Destination)) {
        throw "Base recovery found drifted managed payload; preserving: $Destination"
    }
    Remove-Item -LiteralPath $Destination -Force
}

function Remove-ManagedBaseManifest {
    Assert-NoReparseAncestor -Path $marketManifest
    $item = Get-ExactFileSystemItem -Path $marketManifest
    if ($null -eq $item) { return }
    if ($item.PSIsContainer -or (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Base recovery found an unsafe Marketplace manifest target: $marketManifest"
    }
    $expected = (New-BaseManifest | ConvertTo-Json -Depth 8)
    $actual = [System.IO.File]::ReadAllText($marketManifest)
    if ($actual -ne $expected) {
        throw "Base recovery found a modified Marketplace manifest; preserving: $marketManifest"
    }
    Remove-Item -LiteralPath $marketManifest -Force
}

function Remove-EmptyDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    Assert-NoReparseAncestor -Path $Path
    $item = Get-ExactFileSystemItem -Path $Path
    if ($null -eq $item) { return }
    if (-not $item.PSIsContainer -or (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Base recovery found an unsafe directory target: $Path"
    }
    if (@(Get-ChildItem -LiteralPath $Path -Force).Count -eq 0) {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Remove-PartialBaseInstall {
    Assert-NoReparseAncestor -Path $codexHome
    Assert-NoReparseAncestor -Path $marketRoot
    & $desktopComponent plugin remove 'codex-cross-project-engineering-assistant@cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base recovery could not remove Plugin registration: $LASTEXITCODE" }
    & $desktopComponent plugin marketplace remove 'cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base recovery could not remove Marketplace registration: $LASTEXITCODE" }
    foreach ($name in @('.codex-plugin', 'skills', 'hooks')) {
        Remove-PayloadTree -Source (Join-Path $packageRoot $name) -Destination (Join-Path $pluginRoot $name)
    }
    Remove-ManagedBaseManifest
    Remove-EmptyDirectory -Path $pluginRoot
    Remove-EmptyDirectory -Path (Join-Path $marketRoot 'plugins')
    Remove-EmptyDirectory -Path (Join-Path $marketRoot '.agents\plugins')
    Remove-EmptyDirectory -Path (Join-Path $marketRoot '.agents')
    Remove-EmptyDirectory -Path $marketRoot
    $stateItem = Get-ExactFileSystemItem -Path $baseState
    if ($null -ne $stateItem) {
        Remove-Item -LiteralPath $baseState -Force -ErrorAction Stop
    }
}

Assert-NoReparseAncestor -Path $packageRoot
Assert-NoReparseAncestor -Path $codexHome
Assert-NoReparseAncestor -Path $baseState
Assert-NoReparseAncestor -Path $enhancementState
Assert-NoReparseAncestor -Path $marketRoot
Assert-NoReparseAncestor -Path $pluginRoot
Assert-NoReparseAncestor -Path $marketManifest
if (-not (Test-Path -LiteralPath $desktopComponent -PathType Leaf)) {
    throw 'DESKTOP_COMPONENT_REQUIRED: start Codex Desktop or configure its bundled management component.'
}
 $baseStateItem = Get-ExactFileSystemItem -Path $baseState
 if ($null -ne $baseStateItem) {
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
$enhancementStateItem = Get-ExactFileSystemItem -Path $enhancementState
if ($null -ne $enhancementStateItem) {
    throw 'A managed enhancement installation exists; refusing a base downgrade. Run install-user.ps1.'
}
 $marketRootItem = Get-ExactFileSystemItem -Path $marketRoot
if ($null -ne $marketRootItem -and -not $marketRootItem.PSIsContainer) {
    throw "Base Marketplace path is a file: $marketRoot. Refusing to overwrite unknown files."
}
 $pluginRootItem = Get-ExactFileSystemItem -Path $pluginRoot
if ($null -ne $pluginRootItem) {
    throw "Base Plugin payload directory exists: $pluginRoot. Refusing to overwrite unknown files."
}
 $marketManifestItem = Get-ExactFileSystemItem -Path $marketManifest
if ($null -ne $marketManifestItem) {
    throw "Base Marketplace manifest exists: $marketManifest. Refusing to overwrite unknown files."
}

try {
    Assert-NoReparseAncestor -Path $baseState
    Assert-NoReparseAncestor -Path $pluginRoot
    Assert-NoReparseAncestor -Path $marketManifest
    Write-BaseState -Status 'INSTALLING'
    New-Item -ItemType Directory -Path $pluginRoot -Force | Out-Null
    foreach ($name in @('.codex-plugin', 'skills', 'hooks')) {
        Copy-PayloadTree -Source (Join-Path $packageRoot $name) -Destination (Join-Path $pluginRoot $name)
    }
    $manifest = New-BaseManifest
    $manifestDirectory = Split-Path -Parent $marketManifest
    New-Item -ItemType Directory -Path $manifestDirectory -Force | Out-Null
    Assert-NoReparseAncestor -Path $marketManifest
    [System.IO.File]::WriteAllText($marketManifest, ($manifest | ConvertTo-Json -Depth 8), $utf8NoBom)
    & $desktopComponent plugin marketplace add $marketRoot
    if ($LASTEXITCODE -ne 0) { throw "Codex Marketplace registration failed: $LASTEXITCODE" }
    & $desktopComponent plugin add 'codex-cross-project-engineering-assistant@cp-assistant-base'
    if ($LASTEXITCODE -ne 0) { throw "Base Plugin installation failed: $LASTEXITCODE" }
    & $desktopComponent plugin list --marketplace cp-assistant-base --json
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
