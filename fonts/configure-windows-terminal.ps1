param([string]$SettingsPath = (Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json'))
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $settingsPath) {
    $settings = [IO.File]::ReadAllText($settingsPath)
    # Windows Terminal accepts JSON with comments and trailing commas. Keep
    # quoted strings intact while removing those extensions for PowerShell 5.
    $json = [regex]::Replace($settings, '("(?:\\.|[^"\\])*")|(/\*[\s\S]*?\*/|//[^\r\n]*)', {
        param($match)
        if ($match.Groups[1].Success) { return $match.Value }
        return ' '
    })
    $json = [regex]::Replace($json, '("(?:\\.|[^"\\])*")|,(\s*[}\]])', {
        param($match)
        if ($match.Groups[1].Success) { return $match.Value }
        return $match.Groups[2].Value
    })
    $config = $json | ConvertFrom-Json
    if (-not $config.profiles.PSObject.Properties['defaults']) {
        $config.profiles | Add-Member -NotePropertyName defaults -NotePropertyValue ([pscustomobject]@{})
    }
    $targets = @($config.profiles.defaults)
    foreach ($profile in $config.profiles.list) {
        if ($profile.source -match '^(Microsoft\.WSL|Windows\.Terminal\.Wsl)$' -or
            $profile.font.face -match '^JetBrainsMono (Nerd Font|RunCat)') {
            $targets += $profile
        }
    }
    $changed = $false
    foreach ($profile in $targets) {
        if (-not $profile.PSObject.Properties['font']) {
            $profile | Add-Member -NotePropertyName font -NotePropertyValue ([pscustomobject]@{})
        }
        if ($profile.font.face -ne 'JetBrainsMono RunCat Active') {
            $profile.font | Add-Member -NotePropertyName face -NotePropertyValue 'JetBrainsMono RunCat Active' -Force
            $changed = $true
        }
    }
    if ($changed) {
        $backup = $settingsPath + '.runcat-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak'
        Copy-Item -LiteralPath $settingsPath -Destination $backup
        $updated = $config | ConvertTo-Json -Depth 100
        [IO.File]::WriteAllText($settingsPath, $updated, (New-Object Text.UTF8Encoding $false))
        Write-Output "Windows Terminal settings backup: $backup"
    }
}
