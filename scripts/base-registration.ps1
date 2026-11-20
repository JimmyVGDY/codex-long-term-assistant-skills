# 中文：只读核对桌面插件登记。
# English: Read the native Desktop registration without changing its state.
function Get-BasePluginRegistration {
    param([string]$Component, [string]$PackageRoot)
    $package = 'codex-cross-project-engineering-assistant'
    $market = 'cp-assistant-base'
    $id = "$package@$market"
    try {
        $contract = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PackageRoot 'config/desktop-host-contract-v1.json') | ConvertFrom-Json -ErrorAction Stop
        $profile = $contract.wire_profiles.plugin_json.'plugin-list-v1'
        $version = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PackageRoot '.codex-plugin/plugin.json') | ConvertFrom-Json -ErrorAction Stop).version
        $lines = & $Component plugin list --marketplace $market --json
        if ($LASTEXITCODE -ne 0) { return 'UNVERIFIED' }
        $json = $lines -join [Environment]::NewLine
        if ($json.Length -gt 4194304) { return 'UNVERIFIED' }
        $data = $json | ConvertFrom-Json -ErrorAction Stop
        $names = @($data.PSObject.Properties.Name)
        if ($names.Count -ne 2 -or $names -cnotcontains 'installed' -or $names -cnotcontains 'available' -or
            $data.installed -isnot [array] -or $data.available -isnot [array]) { return 'UNVERIFIED' }
        $target = $null
        foreach ($item in (@($data.installed) + @($data.available))) {
            if ($item -isnot [pscustomobject]) { return 'UNVERIFIED' }
            if ($item.pluginId -ceq $id -or $item.name -ceq $package -or $item.marketplaceName -ceq $market) {
                if ($null -ne $target -or $item.pluginId -cne $id -or $item.name -cne $package -or $item.marketplaceName -cne $market) { return 'IDENTITY_CONFLICT' }
                $target = $item
            }
        }
        if ($null -eq $target) { return 'MISSING' }
        $keys = @($target.PSObject.Properties.Name)
        foreach ($key in $profile.required_target_fields) {
            if ($keys -cnotcontains $key) { return 'UNVERIFIED' }
        }
        foreach ($key in $keys) {
            if ($profile.required_target_fields -ccontains $key) { continue }
            if ($profile.optional_target_fields -cnotcontains $key -or
                ($target.$key -isnot [string] -and $target.$key -isnot [pscustomobject])) { return 'UNVERIFIED' }
        }
        if ($target.installed -isnot [bool] -or $target.enabled -isnot [bool] -or
            $target.version -isnot [string] -or $target.version -cnotmatch '^\d+\.\d+\.\d+$' -or
            $profile.install_policies -cnotcontains $target.installPolicy -or
            $profile.auth_policies -cnotcontains $target.authPolicy) { return 'UNVERIFIED' }
        if ($target.version -cne $version) { return 'VERSION_MISMATCH' }
        if (-not $target.installed) { return 'NOT_INSTALLED' }
        if (-not $target.enabled) { return 'DISABLED' }
        return 'ACTIVE'
    } catch { return 'UNVERIFIED' }
}

function Get-BaseRegistrationAdvice {
    param([string]$Status)
    switch ($Status) {
        'DISABLED' { return 'The Plugin is disabled. Review its enabled setting in Codex Desktop.' }
        'VERSION_MISMATCH' { return 'A different version is registered. Use the managed upgrade path.' }
        'MISSING' { return 'The managed registration is missing. Inspect the Desktop Plugin list before repair.' }
        'NOT_INSTALLED' { return 'The Plugin is available but not installed. Check its Desktop registration.' }
        'IDENTITY_CONFLICT' { return 'Conflicting Plugin identities. Inspect the marketplace and registration.' }
        'ACTIVE' { return 'An active registration already exists. Check its ownership in Codex Desktop.' }
        default { return 'Registration is unverified. Inspect the Plugin list in Codex Desktop.' }
    }
}
