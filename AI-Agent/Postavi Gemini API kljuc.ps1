$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Gemini API kljuc'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object System.Drawing.Size(520, 170)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(20, 18)
$label.Size = New-Object System.Drawing.Size(480, 42)
$label.Text = "Unesi Gemini API kljuc. Kljuc se ne upisuje u projekat ni logove."
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
    [Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $plainKey, 'User')
    [System.Windows.Forms.MessageBox]::Show(
        'Kljuc je spremljen. Nije upisan u projektne fajlove.',
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
