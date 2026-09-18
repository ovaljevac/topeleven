Add-Type -AssemblyName PresentationFramework

$configPath = Join-Path $PSScriptRoot 'discord_config.json'

function Ask-Value {
    param([string]$Title, [string]$Prompt, [switch]$Secret)

    Add-Type -AssemblyName Microsoft.VisualBasic
    if ($Secret) {
        # InputBox ne skriva znakove, pa token trazimo kroz mali PasswordBox prozor.
        [xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="$Title" Width="520" Height="190" WindowStartupLocation="CenterScreen"
        ResizeMode="NoResize" Topmost="True">
  <StackPanel Margin="18">
    <TextBlock TextWrapping="Wrap" Margin="0,0,0,12">$Prompt</TextBlock>
    <PasswordBox Name="ValueBox" Height="30" Margin="0,0,0,14"/>
    <Button Name="OkButton" Content="Nastavi" Width="110" Height="30" HorizontalAlignment="Right"/>
  </StackPanel>
</Window>
"@
        $reader = New-Object System.Xml.XmlNodeReader $xaml
        $window = [Windows.Markup.XamlReader]::Load($reader)
        $box = $window.FindName('ValueBox')
        $window.FindName('OkButton').Add_Click({ $window.DialogResult = $true })
        $box.Add_KeyDown({ if ($_.Key -eq 'Enter') { $window.DialogResult = $true } })
        $window.Add_ContentRendered({ $box.Focus() })
        if ($window.ShowDialog() -ne $true) { return '' }
        return $box.Password.Trim()
    }
    return [Microsoft.VisualBasic.Interaction]::InputBox($Prompt, $Title, '').Trim()
}

$token = Ask-Value -Title 'Discord Bot - token' -Prompt 'Zalijepi bot token iz Discord Developer Portala. Token ostaje samo na ovom racunaru i znakovi su skriveni.' -Secret
if ([string]::IsNullOrWhiteSpace($token)) { exit 1 }

$guildId = Ask-Value -Title 'Discord Bot - server' -Prompt 'Zalijepi Discord Server ID (desni klik na server > Copy Server ID).'
if ($guildId -notmatch '^\d{15,22}$') {
    [MessageBox]::Show('Server ID nije ispravan broj.', 'Discord Bot', 'OK', 'Error') | Out-Null
    exit 1
}

$userId = Ask-Value -Title 'Discord Bot - korisnik' -Prompt 'Zalijepi svoj Discord User ID (desni klik na svoj profil > Copy User ID).'
if ($userId -notmatch '^\d{15,22}$') {
    [MessageBox]::Show('User ID nije ispravan broj.', 'Discord Bot', 'OK', 'Error') | Out-Null
    exit 1
}

$config = [ordered]@{
    token = $token
    guild_id = [UInt64]$guildId
    allowed_user_ids = @([UInt64]$userId)
    live_log = $true
}
$json = $config | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($configPath, $json, [System.Text.UTF8Encoding]::new($false))

[MessageBox]::Show("Konfiguracija je sacuvana.`n`nSada pokreni: Pokreni Discord Bot.cmd", 'Discord Bot', 'OK', 'Information') | Out-Null
