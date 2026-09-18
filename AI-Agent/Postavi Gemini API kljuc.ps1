param(
    [ValidateRange(1, 10)]
    [int]$Slot = 1
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Set-LocalDotEnvSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $envPath = Join-Path $PSScriptRoot '.env'
    $tempPath = Join-Path $PSScriptRoot ('.env.{0}.tmp' -f [guid]::NewGuid().ToString('N'))
    $backupPath = Join-Path $PSScriptRoot ('.env.{0}.bak' -f [guid]::NewGuid().ToString('N'))
    $newLines = [System.Collections.Generic.List[string]]::new()
    $keyPattern = '^\s*{0}\s*=' -f [regex]::Escape($Name)
    $keyWritten = $false

    try {
        if (Test-Path -LiteralPath $envPath) {
            foreach ($line in [System.IO.File]::ReadAllLines($envPath)) {
                if ($line -match $keyPattern) {
                    if (-not $keyWritten) {
                        $newLines.Add("$Name=$Value")
                        $keyWritten = $true
                    }
                    continue
                }
                $newLines.Add($line)
            }
        }
        if (-not $keyWritten) {
            $newLines.Add("$Name=$Value")
        }

        $content = ($newLines -join [Environment]::NewLine) + [Environment]::NewLine
        [System.IO.File]::WriteAllText(
            $tempPath,
            $content,
            [System.Text.UTF8Encoding]::new($false)
        )

        # Temp fajl je u istom folderu, pa je zamjena jedan atomski filesystem
        # korak: agent nikada ne moze procitati napola zapisani API kljuc.
        if (Test-Path -LiteralPath $envPath) {
            [System.IO.File]::Replace($tempPath, $envPath, $backupPath, $true)
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
        else {
            [System.IO.File]::Move($tempPath, $envPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $backupPath) {
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
        $content = $null
        $newLines = $null
    }
}

$form = New-Object System.Windows.Forms.Form
$secretName = if ($Slot -eq 1) { 'GEMINI_API_KEY' } else { "GEMINI_API_KEY_$Slot" }
$slotLabel = if ($Slot -eq 1) { 'glavni' } else { "rezervni #$Slot" }
$form.Text = "Gemini API kljuc - $slotLabel"
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object System.Drawing.Size(520, 170)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(20, 18)
$label.Size = New-Object System.Drawing.Size(480, 42)
$label.Text = "Unesi $slotLabel Gemini API kljuc. Kljuc se lokalno sprema u AI-Agent\.env i nikada se ne ispisuje u logove."
$form.Controls.Add($label)

$textBox = New-Object System.Windows.Forms.TextBox
$textBox.Location = New-Object System.Drawing.Point(20, 66)
$textBox.Size = New-Object System.Drawing.Size(480, 28)
$textBox.UseSystemPasswordChar = $true
$form.Controls.Add($textBox)

$okButton = New-Object System.Windows.Forms.Button
$okButton.Text = 'SPREMI'
$okButton.Location = New-Object System.Drawing.Point(300, 112)
$okButton.Size = New-Object System.Drawing.Size(95, 34)
$okButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $okButton
$form.Controls.Add($okButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = 'ODUSTANI'
$cancelButton.Location = New-Object System.Drawing.Point(405, 112)
$cancelButton.Size = New-Object System.Drawing.Size(95, 34)
$cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.CancelButton = $cancelButton
$form.Controls.Add($cancelButton)

$form.Add_Shown({ $textBox.Focus() })
$result = $form.ShowDialog()

if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
    exit 1
}

$plainKey = $textBox.Text.Trim()
if ([string]::IsNullOrWhiteSpace($plainKey)) {
    [System.Windows.Forms.MessageBox]::Show(
        'Kljuc nije unesen.',
        'Gemini API kljuc',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    ) | Out-Null
    exit 2
}

try {
    Set-LocalDotEnvSecret -Name $secretName -Value $plainKey
    [System.Windows.Forms.MessageBox]::Show(
        "$slotLabel kljuc je sigurno spremljen u lokalni AI-Agent\.env. Agent ga automatski koristi kada prethodni kljuc vrati quota 429.",
        'Gemini API kljuc',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}
finally {
    $textBox.Clear()
    $plainKey = $null
    $form.Dispose()
}
