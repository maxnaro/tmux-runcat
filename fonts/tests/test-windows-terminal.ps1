# Uses temporary settings only; does not install fonts or edit real profiles.
$ErrorActionPreference = 'Stop'
$configure = Join-Path $PSScriptRoot '..\configure-windows-terminal.ps1'
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('runcat-terminal-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $settings = Join-Path $temporary 'settings.json'
    $fixture = @'
{
  // Windows Terminal accepts JSONC.
  "theme": "dark",
  "profiles": {
    "defaults": { "font": { "face": "Original Mono", "size": 12 } },
    "list": [
      { "name": "WSL", "source": "Windows.Terminal.Wsl", },
      { "name": "Matching", "font": { "face": "Original Mono" } },
      { "name": "RunCat", "font": { "face": "Another RunCat v3" } },
      { "name": "Other", "font": { "face": "Unrelated Font", "size": 15 } },
    ],
  },
}
'@
    [IO.File]::WriteAllText($settings, $fixture)
    $family = ([char]0x732b).ToString() + ' Custom Mono'
    & $configure -SettingsPath $settings -FontFamily $family
    $config = [IO.File]::ReadAllText($settings) | ConvertFrom-Json
    if ($config.profiles.defaults.font.face -ne $family) { throw 'Default family was not applied.' }
    if ($config.profiles.defaults.font.size -ne 12 -or $config.theme -ne 'dark') {
        throw 'Unrelated settings changed.'
    }
    foreach ($profile in $config.profiles.list) {
        if ($profile.name -eq 'Other') {
            if ($profile.font.face -ne 'Unrelated Font' -or $profile.font.size -ne 15) {
                throw 'Unrelated profile changed.'
            }
        } elseif ($profile.font.face -ne $family) {
            throw "Family was not applied to $($profile.name)."
        }
    }
    $before = [IO.File]::ReadAllText($settings)
    $backupCount = @(Get-ChildItem -LiteralPath $temporary -Filter '*.bak').Count
    & $configure -SettingsPath $settings -FontFamily $family
    if ([IO.File]::ReadAllText($settings) -cne $before -or
        @(Get-ChildItem -LiteralPath $temporary -Filter '*.bak').Count -ne $backupCount) {
        throw 'Repeated configuration was not idempotent.'
    }
    & $configure -SettingsPath $settings -FontFamily 'Second Custom Mono'
    $config = [IO.File]::ReadAllText($settings) | ConvertFrom-Json
    if ($config.profiles.list[1].font.face -ne 'Second Custom Mono') {
        throw 'A previous custom family was not updated.'
    }
    Write-Output 'PASS: custom family, Unicode, JSONC, preserved settings, and repeated setup'
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force
}
