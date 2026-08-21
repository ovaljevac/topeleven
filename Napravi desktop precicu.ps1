$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$activeDirectory = Join-Path $projectDirectory 'AI-Agent'
$launcher = Join-Path $activeDirectory 'Pokreni AI Agent.cmd'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Top Eleven Agent.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $activeDirectory
$shortcut.Description = 'Pokreni Top Eleven Agent'
$shortcut.Save()

[System.Windows.Forms.MessageBox]::Show(
    "Prečica je napravljena na Desktopu:`r`n$shortcutPath",
    'Top Eleven Agent'
) | Out-Null
