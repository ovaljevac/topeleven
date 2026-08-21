param(
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'

$script:AgentScript = Join-Path $PSScriptRoot 'TopElevenAgent.ps1'
$script:ModeCatalog = @(
    [PSCustomObject]@{ Mode = 'Zeleni';          Name = 'Uzmi 25 zelenih';       Description = 'Preuzima sve dostupne besplatne zelene boostere.'; Accent = '#2F80ED' },
    [PSCustomObject]@{ Mode = 'OdmoriEkipu';    Name = 'Odmori ekipu';          Description = 'Odmara igrace redom od izabrane pocetne pozicije.'; Accent = '#20B26B' },
    [PSCustomObject]@{ Mode = 'TV';              Name = 'Top Eleven TV';         Description = 'Preuzima TV nagrade i zavrsava tok prirucnika.'; Accent = '#7B61FF' },
    [PSCustomObject]@{ Mode = 'Mourinho';        Name = 'Mourinho';              Description = 'Pokrece Mourinho nagradnu reklamu.'; Accent = '#E8A317' },
    [PSCustomObject]@{ Mode = 'Kampus';          Name = 'Kampus';                Description = 'Obradjuje Kampus objekte koji jos nisu na 100%.'; Accent = '#19A7A0' },
    [PSCustomObject]@{ Mode = 'PutSaveza';       Name = 'Put saveza';            Description = 'Zavrsava dnevni video zadatak na Putu saveza.'; Accent = '#D95D8C' },
    [PSCustomObject]@{ Mode = 'TreningIgraca';   Name = 'Trening igraca';        Description = 'Ponavlja trening i po potrebi podize kondiciju igraca.'; Accent = '#E26A3B' },
    [PSCustomObject]@{ Mode = 'Sve';             Name = 'Pokreni sve';           Description = 'Mourinho, TV, Put saveza, Kampus i 25 zelenih.'; Accent = '#246BFD' }
)
$script:CombinedStartCatalog = @(
    [PSCustomObject]@{ Key = 'Mourinho';  Name = 'Mourinho' },
    [PSCustomObject]@{ Key = 'TV';        Name = 'Top Eleven TV' },
    [PSCustomObject]@{ Key = 'PutSaveza'; Name = 'Put saveza' },
    [PSCustomObject]@{ Key = 'Kampus';    Name = 'Kampus' },
    [PSCustomObject]@{ Key = 'Zeleni';    Name = 'Uzmi 25 zelenih' }
)
$script:TeamRestStartCatalog = @(
    [PSCustomObject]@{ Key = 'GK';    Name = 'GK' },
    [PSCustomObject]@{ Key = 'DL';    Name = 'DL' },
    [PSCustomObject]@{ Key = 'DC1';   Name = 'DC 1' },
    [PSCustomObject]@{ Key = 'DC2';   Name = 'DC 2' },
    [PSCustomObject]@{ Key = 'DR';    Name = 'DR' },
    [PSCustomObject]@{ Key = 'DMC';   Name = 'DMC' },
    [PSCustomObject]@{ Key = 'MC1';   Name = 'MC 1' },
    [PSCustomObject]@{ Key = 'MC2';   Name = 'MC 2' },
    [PSCustomObject]@{ Key = 'AML';   Name = 'AML' },
    [PSCustomObject]@{ Key = 'AMR';   Name = 'AMR' },
    [PSCustomObject]@{ Key = 'ST';    Name = 'ST' },
    [PSCustomObject]@{ Key = 'DL_2';  Name = 'DL (drugi krug)' },
    [PSCustomObject]@{ Key = 'ST_2';  Name = 'ST (drugi krug)' },
    [PSCustomObject]@{ Key = 'AMR_2'; Name = 'AMR (drugi krug)' },
    [PSCustomObject]@{ Key = 'AML_2'; Name = 'AML (drugi krug)' }
)

function Get-AgentArgumentTokens {
    param(
        [Parameter(Mandatory = $true)][string]$Mode,
        [string]$CombinedStartStage = 'Mourinho',
        [string]$TeamRestStart = 'GK',
        [string]$LogPath = 'manager.log',
        [string]$StopSignalPath = 'manager.stop'
    )

    if ($Mode -notin @($script:ModeCatalog.Mode)) {
        throw "Nepoznat mod: $Mode"
    }

    $tokens = @(
        '-NoProfile',
        '-STA',
        '-ExecutionPolicy', 'Bypass',
        '-File', $script:AgentScript,
        '-Mode', $Mode,
        '-AutoStart',
        '-ExitAfterRun',
        '-LogPath', $LogPath,
        '-StopSignalPath', $StopSignalPath
    )
    if ($Mode -eq 'Sve') {
        if ($CombinedStartStage -notin @($script:CombinedStartCatalog.Key)) {
            throw "Nepoznata pocetna faza: $CombinedStartStage"
        }
        $tokens += @('-CombinedStartStage', $CombinedStartStage)
    }
    if ($Mode -eq 'OdmoriEkipu') {
        if ($TeamRestStart -notin @($script:TeamRestStartCatalog.Key)) {
            throw "Nepoznata pocetna pozicija: $TeamRestStart"
        }
        $tokens += @('-TeamRestStart', $TeamRestStart)
    }
    return ,$tokens
}

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

if ($SelfTest) {
    "Manager agent script exists: $(Test-Path -LiteralPath $script:AgentScript)"
    foreach ($item in $script:ModeCatalog) {
        "MODE|$($item.Mode)|$($item.Name)"
    }
    "COMBINED_START|$((@($script:CombinedStartCatalog.Key)) -join ',')"
    "TEAM_REST_START|$((@($script:TeamRestStartCatalog.Key)) -join ',')"
    $sample = Get-AgentArgumentTokens -Mode 'Sve' -CombinedStartStage 'PutSaveza' -LogPath 'sample.log' -StopSignalPath 'sample.stop'
    "SAMPLE|$($sample -join ' ')"
    exit 0
}

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName WindowsBase

[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        x:Name="ManagerWindow"
        Title="Top Eleven AI Agent Manager"
        Width="1220" Height="790" MinWidth="1010" MinHeight="680"
        WindowStartupLocation="CenterScreen"
        WindowStyle="None" ResizeMode="CanResize"
        Background="#F4F7FB" Foreground="#172033"
        FontFamily="Segoe UI">
    <Window.Resources>
        <SolidColorBrush x:Key="PanelBrush" Color="#FFFFFF"/>
        <SolidColorBrush x:Key="CardBrush" Color="#FFFFFF"/>
        <SolidColorBrush x:Key="BorderBrush" Color="#D5DEE9"/>
        <SolidColorBrush x:Key="MutedBrush" Color="#56657A"/>
        <SolidColorBrush x:Key="BlueBrush" Color="#1769E0"/>
        <Style TargetType="Button" x:Key="RoundedButton">
            <Setter Property="Foreground" Value="#172033"/>
            <Setter Property="Background" Value="#E9EFF6"/>
            <Setter Property="BorderBrush" Value="#C8D3E0"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="Padding" Value="18,10"/>
            <Setter Property="FontSize" Value="14"/>
            <Setter Property="FontWeight" Value="SemiBold"/>
            <Setter Property="HorizontalContentAlignment" Value="Center"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Cursor" Value="Hand"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border x:Name="ButtonBorder" Background="{TemplateBinding Background}"
                                BorderBrush="{TemplateBinding BorderBrush}"
                                BorderThickness="{TemplateBinding BorderThickness}"
                                CornerRadius="8" Padding="{TemplateBinding Padding}">
                            <ContentPresenter HorizontalAlignment="{TemplateBinding HorizontalContentAlignment}"
                                              VerticalAlignment="{TemplateBinding VerticalContentAlignment}"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsMouseOver" Value="True">
                                <Setter TargetName="ButtonBorder" Property="Opacity" Value="0.86"/>
                            </Trigger>
                            <Trigger Property="IsPressed" Value="True">
                                <Setter TargetName="ButtonBorder" Property="Opacity" Value="0.70"/>
                            </Trigger>
                            <Trigger Property="IsEnabled" Value="False">
                                <Setter TargetName="ButtonBorder" Property="Opacity" Value="0.38"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>
        <Style TargetType="Button" x:Key="NavButton" BasedOn="{StaticResource RoundedButton}">
            <Setter Property="Foreground" Value="#334155"/>
            <Setter Property="Background" Value="Transparent"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="HorizontalContentAlignment" Value="Left"/>
            <Setter Property="Padding" Value="18,13"/>
            <Setter Property="Margin" Value="0,3"/>
        </Style>
        <Style TargetType="ComboBox">
            <Setter Property="Background" Value="#FFFFFF"/>
            <Setter Property="Foreground" Value="#172033"/>
            <Setter Property="BorderBrush" Value="#B8C5D4"/>
            <Setter Property="Padding" Value="10,7"/>
            <Setter Property="FontSize" Value="14"/>
        </Style>
        <Style TargetType="ListBoxItem">
            <Setter Property="Foreground" Value="#172033"/>
            <Setter Property="Background" Value="Transparent"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Padding" Value="0"/>
            <Setter Property="Margin" Value="0,0,0,9"/>
            <Setter Property="HorizontalContentAlignment" Value="Stretch"/>
            <Style.Triggers>
                <Trigger Property="IsSelected" Value="True">
                    <Setter Property="Background" Value="#DDEAFF"/>
                </Trigger>
            </Style.Triggers>
        </Style>
    </Window.Resources>

    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="58"/>
            <RowDefinition Height="*"/>
        </Grid.RowDefinitions>
        <Grid.ColumnDefinitions>
            <ColumnDefinition Width="245"/>
            <ColumnDefinition Width="*"/>
        </Grid.ColumnDefinitions>

        <Border Grid.Row="0" Grid.ColumnSpan="2" Background="#FFFFFF" BorderBrush="#D5DEE9" BorderThickness="1,1,1,1">
            <Grid x:Name="HeaderDragArea">
                <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="150"/></Grid.ColumnDefinitions>
                <StackPanel Orientation="Horizontal" Margin="22,0,0,0" VerticalAlignment="Center">
                    <Border Width="32" Height="32" CornerRadius="9" Background="#DDEAFF">
                        <TextBlock Text="AI" Foreground="#145CC5" FontWeight="Bold" FontSize="12" HorizontalAlignment="Center" VerticalAlignment="Center"/>
                    </Border>
                    <TextBlock Text="Top Eleven AI Agent Manager" FontSize="16" FontWeight="SemiBold" Margin="11,0,0,0" VerticalAlignment="Center"/>
                </StackPanel>
                <StackPanel Grid.Column="1" Orientation="Horizontal" HorizontalAlignment="Right">
                    <Button x:Name="WindowMinimize" Style="{StaticResource RoundedButton}" Width="48" Height="38" Padding="0" Background="Transparent" BorderThickness="0" Content="&#x2014;"/>
                    <Button x:Name="WindowMaximize" Style="{StaticResource RoundedButton}" Width="48" Height="38" Padding="0" Background="Transparent" BorderThickness="0" Content="&#x25A1;"/>
                    <Button x:Name="WindowClose" Style="{StaticResource RoundedButton}" Width="48" Height="38" Padding="0" Background="Transparent" BorderThickness="0" Content="X"/>
                </StackPanel>
            </Grid>
        </Border>

        <Border Grid.Row="1" Grid.Column="0" Background="#FFFFFF" BorderBrush="#D5DEE9" BorderThickness="0,0,1,1">
            <Grid Margin="22,24,22,20">
                <Grid.RowDefinitions>
                    <RowDefinition Height="58"/>
                    <RowDefinition Height="*"/>
                    <RowDefinition Height="96"/>
                    <RowDefinition Height="30"/>
                </Grid.RowDefinitions>
                <StackPanel Grid.Row="0" Orientation="Horizontal">
                    <Border Width="42" Height="42" CornerRadius="12" Background="#DDEAFF">
                        <TextBlock Text="AI" Foreground="#145CC5" FontWeight="Bold" FontSize="16"
                                   HorizontalAlignment="Center" VerticalAlignment="Center"/>
                    </Border>
                    <TextBlock Text="AI Agent Manager" FontSize="18" FontWeight="SemiBold"
                               VerticalAlignment="Center" Margin="12,0,0,0"/>
                </StackPanel>

                <StackPanel Grid.Row="1" Margin="0,18,0,0">
                    <Button x:Name="NavDashboard" Style="{StaticResource NavButton}" Background="#DDEAFF" Foreground="#124EAA" Content="  Dashboard"/>
                    <Button x:Name="NavScripts" Style="{StaticResource NavButton}" Content="  Skripte"/>
                    <Button x:Name="NavLogs" Style="{StaticResource NavButton}" Content="  Logovi"/>
                    <Button x:Name="NavSettings" Style="{StaticResource NavButton}" Content="  Postavke"/>
                </StackPanel>

                <Border Grid.Row="2" Background="#F7F9FC" BorderBrush="#D5DEE9" BorderThickness="1" CornerRadius="10" Padding="14">
                    <Grid>
                        <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="38"/></Grid.ColumnDefinitions>
                        <StackPanel>
                            <StackPanel Orientation="Horizontal">
                                <Ellipse x:Name="SidebarStatusDot" Width="10" Height="10" Fill="#34C77B" Margin="0,3,9,0"/>
                                <TextBlock Text="Agent status" FontSize="13"/>
                            </StackPanel>
                            <TextBlock x:Name="SidebarStatusText" Text="Spreman" Foreground="#34C77B" FontSize="16" Margin="19,7,0,0"/>
                        </StackPanel>
                        <Border Grid.Column="1" Width="34" Height="34" CornerRadius="17" Background="#E5EBF3" VerticalAlignment="Center">
                            <TextBlock Text="AI" FontWeight="Bold" FontSize="11" HorizontalAlignment="Center" VerticalAlignment="Center"/>
                        </Border>
                    </Grid>
                </Border>
                <TextBlock Grid.Row="3" Text="ver. 1.0.0" Foreground="#718096" FontSize="12" VerticalAlignment="Bottom"/>
            </Grid>
        </Border>

        <TabControl x:Name="MainTabs" Grid.Row="1" Grid.Column="1" Background="Transparent" BorderThickness="0" Margin="0">
            <TabControl.Resources>
                <Style TargetType="TabItem"><Setter Property="Visibility" Value="Collapsed"/></Style>
            </TabControl.Resources>

            <TabItem Header="Dashboard">
                <ScrollViewer VerticalScrollBarVisibility="Auto">
                    <StackPanel Margin="32,28,32,30">
                        <TextBlock Text="Dashboard" FontSize="30" FontWeight="Bold"/>
                        <TextBlock Text="Upravljajte svojim Top Eleven AI agentom" Foreground="{StaticResource MutedBrush}" FontSize="15" Margin="0,5,0,25"/>

                        <Border Background="{StaticResource CardBrush}" BorderBrush="{StaticResource BorderBrush}" BorderThickness="1" CornerRadius="11" Padding="26">
                            <Grid>
                                <Grid.ColumnDefinitions><ColumnDefinition Width="82"/><ColumnDefinition Width="*"/><ColumnDefinition Width="225"/></Grid.ColumnDefinitions>
                                <Border Width="68" Height="68" CornerRadius="34" Background="#E2ECFF" HorizontalAlignment="Left">
                                    <TextBlock Text="AI" Foreground="#1761C5" FontSize="24" FontWeight="Bold" HorizontalAlignment="Center" VerticalAlignment="Center"/>
                                </Border>
                                <StackPanel Grid.Column="1" VerticalAlignment="Center">
                                    <TextBlock x:Name="DashboardAgentTitle" Text="Top Eleven AI Agent" FontSize="21" FontWeight="SemiBold"/>
                                    <Border Background="#E4F6EC" BorderBrush="#BFE7D0" BorderThickness="1" CornerRadius="14" Padding="10,4" HorizontalAlignment="Left" Margin="0,8,0,0">
                                        <StackPanel Orientation="Horizontal">
                                            <Ellipse x:Name="DashboardStatusDot" Width="9" Height="9" Fill="#34C77B" Margin="0,4,7,0"/>
                                            <TextBlock x:Name="DashboardStatusText" Text="Spreman" Foreground="#118A52" FontSize="13" FontWeight="SemiBold"/>
                                        </StackPanel>
                                    </Border>
                                    <TextBlock x:Name="DashboardDescription" Text="Izaberite skriptu i pokrenite automatizaciju." Foreground="{StaticResource MutedBrush}" Margin="0,9,0,0"/>
                                </StackPanel>
                                <StackPanel Grid.Column="2" VerticalAlignment="Center">
                                    <Button x:Name="DashboardStart" Style="{StaticResource RoundedButton}" Foreground="White" Background="#1769E0" BorderBrush="#1769E0" Content="Pokreni agenta"/>
                                    <Button x:Name="DashboardStop" Style="{StaticResource RoundedButton}" Margin="0,10,0,0" Content="Zaustavi agenta" IsEnabled="False"/>
                                </StackPanel>
                            </Grid>
                        </Border>

                        <TextBlock Text="Brze akcije" FontSize="18" FontWeight="SemiBold" Margin="0,25,0,14"/>
                        <Grid>
                            <Grid.ColumnDefinitions>
                                <ColumnDefinition Width="*"/><ColumnDefinition Width="14"/><ColumnDefinition Width="*"/><ColumnDefinition Width="14"/><ColumnDefinition Width="*"/>
                            </Grid.ColumnDefinitions>
                            <Button x:Name="QuickScripts" Grid.Column="0" Style="{StaticResource RoundedButton}" Height="94" HorizontalContentAlignment="Left" Content="IZABERI SKRIPTU&#x0a;Pojedinacni i kompletni tokovi"/>
                            <Button x:Name="QuickAll" Grid.Column="2" Style="{StaticResource RoundedButton}" Height="94" HorizontalContentAlignment="Left" Background="#E7F6ED" BorderBrush="#B7DEC6" Content="POKRENI SVE&#x0a;Izaberi pocetnu fazu"/>
                            <Button x:Name="QuickLogs" Grid.Column="4" Style="{StaticResource RoundedButton}" Height="94" HorizontalContentAlignment="Left" Background="#FFF4D6" BorderBrush="#E6CF89" Content="OTVORI LOGOVE&#x0a;Prati aktivnost agenta"/>
                        </Grid>

                        <TextBlock Text="Nedavne aktivnosti" FontSize="18" FontWeight="SemiBold" Margin="0,25,0,14"/>
                        <Border Background="{StaticResource CardBrush}" BorderBrush="{StaticResource BorderBrush}" BorderThickness="1" CornerRadius="11" Padding="18" MinHeight="150">
                            <TextBox x:Name="DashboardRecentLog" IsReadOnly="True" Background="Transparent" BorderThickness="0"
                                     Foreground="#334155" FontFamily="Consolas" FontSize="12" TextWrapping="Wrap"
                                     VerticalScrollBarVisibility="Auto"/>
                        </Border>
                    </StackPanel>
                </ScrollViewer>
            </TabItem>

            <TabItem Header="Skripte">
                <Grid Margin="32,28,32,30">
                    <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions>
                    <StackPanel>
                        <TextBlock Text="Skripte" FontSize="30" FontWeight="Bold"/>
                        <TextBlock Text="Izaberite tacno koji automatizovani tok zelite pokrenuti" Foreground="{StaticResource MutedBrush}" FontSize="15" Margin="0,5,0,22"/>
                    </StackPanel>
                    <Grid Grid.Row="1">
                        <Grid.ColumnDefinitions><ColumnDefinition Width="1.25*"/><ColumnDefinition Width="18"/><ColumnDefinition Width="0.9*"/></Grid.ColumnDefinitions>
                        <Border Background="{StaticResource CardBrush}" BorderBrush="{StaticResource BorderBrush}" BorderThickness="1" CornerRadius="11" Padding="14">
                            <ListBox x:Name="ScriptList" Background="Transparent" BorderThickness="0" ScrollViewer.VerticalScrollBarVisibility="Auto">
                                <ListBox.ItemTemplate>
                                    <DataTemplate>
                                        <Border x:Name="ScriptCard" Background="#F8FAFD" BorderBrush="#D6DFEA" BorderThickness="1" CornerRadius="8" Padding="14">
                                            <Grid>
                                                <Grid.ColumnDefinitions><ColumnDefinition Width="8"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
                                                <Border Background="{Binding Accent}" CornerRadius="4"/>
                                                <StackPanel Grid.Column="1" Margin="13,0,0,0">
                                                    <TextBlock Text="{Binding Name}" FontSize="16" FontWeight="SemiBold"/>
                                                    <TextBlock Text="{Binding Description}" Foreground="#526174" FontSize="12" Margin="0,4,0,0" TextWrapping="Wrap"/>
                                                </StackPanel>
                                            </Grid>
                                        </Border>
                                        <DataTemplate.Triggers>
                                            <DataTrigger Binding="{Binding RelativeSource={RelativeSource AncestorType=ListBoxItem}, Path=IsSelected}" Value="True">
                                                <Setter TargetName="ScriptCard" Property="Background" Value="#E8F1FF"/>
                                                <Setter TargetName="ScriptCard" Property="BorderBrush" Value="#1769E0"/>
                                                <Setter TargetName="ScriptCard" Property="BorderThickness" Value="2"/>
                                            </DataTrigger>
                                        </DataTemplate.Triggers>
                                    </DataTemplate>
                                </ListBox.ItemTemplate>
                            </ListBox>
                        </Border>

                        <Border Grid.Column="2" Background="{StaticResource CardBrush}" BorderBrush="{StaticResource BorderBrush}" BorderThickness="1" CornerRadius="11" Padding="22">
                            <StackPanel>
                                <TextBlock Text="Odabrana skripta" Foreground="{StaticResource MutedBrush}" FontSize="13"/>
                                <TextBlock x:Name="SelectedScriptName" Text="Uzmi 25 zelenih" FontSize="22" FontWeight="SemiBold" Margin="0,6,0,0"/>
                                <TextBlock x:Name="SelectedScriptDescription" Foreground="#526174" TextWrapping="Wrap" Margin="0,8,0,22"/>

                                <StackPanel x:Name="CombinedStartPanel" Visibility="Collapsed">
                                    <TextBlock Text="Pokreni sve od faze:" FontSize="13" Margin="0,0,0,7"/>
                                    <ComboBox x:Name="CombinedStartCombo" DisplayMemberPath="Name" SelectedValuePath="Key" Margin="0,0,0,18"/>
                                </StackPanel>
                                <StackPanel x:Name="TeamRestStartPanel" Visibility="Collapsed">
                                    <TextBlock Text="Odmori ekipu od pozicije:" FontSize="13" Margin="0,0,0,7"/>
                                    <ComboBox x:Name="TeamRestStartCombo" DisplayMemberPath="Name" SelectedValuePath="Key" Margin="0,0,0,18"/>
                                </StackPanel>

                                <Border Background="#F7F9FC" BorderBrush="#D5DEE9" BorderThickness="1" CornerRadius="8" Padding="13" Margin="0,0,0,20">
                                    <StackPanel>
                                        <TextBlock Text="Status" Foreground="{StaticResource MutedBrush}" FontSize="12"/>
                                        <TextBlock x:Name="SelectedStatusText" Text="Spreman za pokretanje" Foreground="#118A52" FontWeight="SemiBold" FontSize="14" Margin="0,5,0,0" TextWrapping="Wrap"/>
                                    </StackPanel>
                                </Border>

                                <Button x:Name="ScriptsStart" Style="{StaticResource RoundedButton}" Foreground="White" Background="#1769E0" BorderBrush="#1769E0" Content="Pokreni odabranu skriptu"/>
                                <Button x:Name="ScriptsStop" Style="{StaticResource RoundedButton}" Margin="0,10,0,0" Content="Zaustavi agenta" IsEnabled="False"/>
                            </StackPanel>
                        </Border>
                    </Grid>
                </Grid>
            </TabItem>

            <TabItem Header="Logovi">
                <Grid Margin="32,28,32,30">
                    <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions>
                    <TextBlock Text="Logovi" FontSize="30" FontWeight="Bold"/>
                    <Grid Grid.Row="1" Margin="0,14,0,14">
                        <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/><ColumnDefinition Width="10"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
                        <TextBlock x:Name="LogPathText" Text="Nema aktivnog loga" Foreground="{StaticResource MutedBrush}" VerticalAlignment="Center" TextTrimming="CharacterEllipsis"/>
                        <Button x:Name="OpenLogFolder" Grid.Column="1" Style="{StaticResource RoundedButton}" Padding="14,7" Content="Otvori folder"/>
                        <Button x:Name="ClearLogView" Grid.Column="3" Style="{StaticResource RoundedButton}" Padding="14,7" Content="Ocisti prikaz"/>
                    </Grid>
                    <Border Grid.Row="2" Background="#101826" BorderBrush="#26364D" BorderThickness="1" CornerRadius="10" Padding="12">
                        <TextBox x:Name="LogTextBox" IsReadOnly="True" Background="Transparent" BorderThickness="0"
                                 Foreground="#E4EBF5" FontFamily="Consolas" FontSize="13" TextWrapping="NoWrap"
                                 HorizontalScrollBarVisibility="Auto" VerticalScrollBarVisibility="Auto"/>
                    </Border>
                </Grid>
            </TabItem>

            <TabItem Header="Postavke">
                <StackPanel Margin="32,28,32,30">
                    <TextBlock Text="Postavke" FontSize="30" FontWeight="Bold"/>
                    <TextBlock Text="AI kljuc, provjera modela i lokalni podaci managera" Foreground="{StaticResource MutedBrush}" FontSize="15" Margin="0,5,0,24"/>
                    <Border Background="{StaticResource CardBrush}" BorderBrush="{StaticResource BorderBrush}" BorderThickness="1" CornerRadius="11" Padding="22" MaxWidth="720" HorizontalAlignment="Left">
                        <StackPanel>
                            <TextBlock Text="Gemini AI" FontSize="19" FontWeight="SemiBold"/>
                            <TextBlock Text="API kljuc ostaje u lokalnom .env fajlu i ne prikazuje se u manageru." Foreground="{StaticResource MutedBrush}" Margin="0,7,0,18"/>
                            <WrapPanel>
                                <Button x:Name="ConfigureGemini" Style="{StaticResource RoundedButton}" Foreground="White" Background="#1769E0" BorderBrush="#1769E0" Content="Postavi API kljuc" Margin="0,0,10,0"/>
                                <Button x:Name="TestGemini" Style="{StaticResource RoundedButton}" Content="Testiraj Gemini"/>
                            </WrapPanel>
                            <Separator Background="#D8E0EA" Margin="0,22"/>
                            <TextBlock Text="Radni folder" FontSize="19" FontWeight="SemiBold"/>
                            <TextBlock x:Name="WorkingFolderText" Foreground="{StaticResource MutedBrush}" Margin="0,7,0,14" TextWrapping="Wrap"/>
                            <Button x:Name="OpenWorkingFolder" Style="{StaticResource RoundedButton}" HorizontalAlignment="Left" Content="Otvori AI-Agent folder"/>
                        </StackPanel>
                    </Border>
                </StackPanel>
            </TabItem>
        </TabControl>
    </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)

function Find-Control {
    param([string]$Name)
    return $window.FindName($Name)
}

$mainTabs = Find-Control 'MainTabs'
$scriptList = Find-Control 'ScriptList'
$combinedStartCombo = Find-Control 'CombinedStartCombo'
$teamRestStartCombo = Find-Control 'TeamRestStartCombo'
$combinedStartPanel = Find-Control 'CombinedStartPanel'
$teamRestStartPanel = Find-Control 'TeamRestStartPanel'
$selectedScriptName = Find-Control 'SelectedScriptName'
$selectedScriptDescription = Find-Control 'SelectedScriptDescription'
$selectedStatusText = Find-Control 'SelectedStatusText'
$dashboardAgentTitle = Find-Control 'DashboardAgentTitle'
$dashboardDescription = Find-Control 'DashboardDescription'
$dashboardStatusText = Find-Control 'DashboardStatusText'
$dashboardStatusDot = Find-Control 'DashboardStatusDot'
$sidebarStatusText = Find-Control 'SidebarStatusText'
$sidebarStatusDot = Find-Control 'SidebarStatusDot'
$logTextBox = Find-Control 'LogTextBox'
$dashboardRecentLog = Find-Control 'DashboardRecentLog'
$logPathText = Find-Control 'LogPathText'
$dashboardStart = Find-Control 'DashboardStart'
$dashboardStop = Find-Control 'DashboardStop'
$scriptsStart = Find-Control 'ScriptsStart'
$scriptsStop = Find-Control 'ScriptsStop'
$navButtons = @(
    (Find-Control 'NavDashboard'),
    (Find-Control 'NavScripts'),
    (Find-Control 'NavLogs'),
    (Find-Control 'NavSettings')
)

$scriptList.ItemsSource = $script:ModeCatalog
$scriptList.SelectedIndex = 0
$combinedStartCombo.ItemsSource = $script:CombinedStartCatalog
$combinedStartCombo.SelectedIndex = 0
$teamRestStartCombo.ItemsSource = $script:TeamRestStartCatalog
$teamRestStartCombo.SelectedIndex = 0
(Find-Control 'WorkingFolderText').Text = $PSScriptRoot

$script:AgentProcess = $null
$script:CurrentLogPath = $null
$script:CurrentStopSignalPath = $null
$script:DisplayedLogLineCount = 0
$script:StopRequestedAt = $null
$script:StopWasRequested = $false
$script:CloseRequested = $false
$script:LastExitHandledProcessId = $null
$script:LogsRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'TopElevenAgent\logs'
[System.IO.Directory]::CreateDirectory($script:LogsRoot) | Out-Null

function Set-NavigationPage {
    param([int]$Index)
    $mainTabs.SelectedIndex = $Index
    $brushConverter = [System.Windows.Media.BrushConverter]::new()
    for ($i = 0; $i -lt $navButtons.Count; $i++) {
        $navButtons[$i].Background = [System.Windows.Media.Brushes]::Transparent
        $navButtons[$i].Foreground = $brushConverter.ConvertFromString('#334155')
        if ($i -eq $Index) {
            $navButtons[$i].Background = $brushConverter.ConvertFromString('#DDEAFF')
            $navButtons[$i].Foreground = $brushConverter.ConvertFromString('#124EAA')
        }
    }
}

function Set-ManagerState {
    param(
        [string]$Text,
        [ValidateSet('Ready', 'Running', 'Stopping', 'Success', 'Error')]
        [string]$Kind = 'Ready'
    )

    $colors = @{
        Ready = '#118A52'; Running = '#118A52'; Stopping = '#A66600'; Success = '#1769E0'; Error = '#C73745'
    }
    $brush = [System.Windows.Media.BrushConverter]::new().ConvertFromString($colors[$Kind])
    $dashboardStatusText.Text = $Text
    $dashboardStatusText.Foreground = $brush
    $dashboardStatusDot.Fill = $brush
    $sidebarStatusText.Text = $Text
    $sidebarStatusText.Foreground = $brush
    $sidebarStatusDot.Fill = $brush
    $selectedStatusText.Text = $Text
    $selectedStatusText.Foreground = $brush
}

function Test-AgentRunning {
    if ($null -eq $script:AgentProcess) { return $false }
    try { return -not $script:AgentProcess.HasExited } catch { return $false }
}

function Set-RunButtons {
    param([bool]$Running)
    $dashboardStart.IsEnabled = -not $Running
    $scriptsStart.IsEnabled = -not $Running
    $dashboardStop.IsEnabled = $Running
    $scriptsStop.IsEnabled = $Running
    $scriptList.IsEnabled = -not $Running
    $combinedStartCombo.IsEnabled = -not $Running
    $teamRestStartCombo.IsEnabled = -not $Running
}

function Update-SelectedScript {
    $selected = $scriptList.SelectedItem
    if ($null -eq $selected) { return }
    $selectedScriptName.Text = [string]$selected.Name
    $selectedScriptDescription.Text = [string]$selected.Description
    $dashboardAgentTitle.Text = [string]$selected.Name
    $dashboardDescription.Text = [string]$selected.Description
    $combinedStartPanel.Visibility = if ([string]$selected.Mode -eq 'Sve') { 'Visible' } else { 'Collapsed' }
    $teamRestStartPanel.Visibility = if ([string]$selected.Mode -eq 'OdmoriEkipu') { 'Visible' } else { 'Collapsed' }
}

function Add-ManagerLogLine {
    param([string]$Text)
    $stamp = Get-Date -Format 'HH:mm:ss'
    $line = "[$stamp] MANAGER: $Text"
    if ($null -ne $script:CurrentLogPath) {
        try { [System.IO.File]::AppendAllText($script:CurrentLogPath, "$line`r`n", [System.Text.UTF8Encoding]::new($false)) } catch { }
    }
    $logTextBox.AppendText("$line`r`n")
    $logTextBox.ScrollToEnd()
}

function Update-LogViews {
    if ($null -eq $script:CurrentLogPath -or -not (Test-Path -LiteralPath $script:CurrentLogPath)) { return }
    try {
        $lines = [System.IO.File]::ReadAllLines($script:CurrentLogPath)
        if ($lines.Count -ne $script:DisplayedLogLineCount) {
            $logTextBox.Text = $lines -join "`r`n"
            if ($lines.Count -gt 0) { $logTextBox.AppendText("`r`n") }
            $logTextBox.ScrollToEnd()
            $recentStart = [Math]::Max(0, $lines.Count - 10)
            $dashboardRecentLog.Text = @($lines[$recentStart..([Math]::Max($recentStart, $lines.Count - 1))]) -join "`r`n"
            $dashboardRecentLog.ScrollToEnd()
            $script:DisplayedLogLineCount = $lines.Count
        }
    }
    catch { }
}

function Start-SelectedAgent {
    if (Test-AgentRunning) { return }
    $selected = $scriptList.SelectedItem
    if ($null -eq $selected) { return }
    if (-not (Test-Path -LiteralPath $script:AgentScript)) {
        [System.Windows.MessageBox]::Show('TopElevenAgent.ps1 nije pronadjen.', 'AI Agent Manager', 'OK', 'Error') | Out-Null
        return
    }

    $mode = [string]$selected.Mode
    $combinedStart = if ($combinedStartCombo.SelectedValue) { [string]$combinedStartCombo.SelectedValue } else { 'Mourinho' }
    $teamRestStart = if ($teamRestStartCombo.SelectedValue) { [string]$teamRestStartCombo.SelectedValue } else { 'GK' }
    $runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $script:CurrentLogPath = Join-Path $script:LogsRoot "run-$runId-$mode.log"
    $script:CurrentStopSignalPath = Join-Path $script:LogsRoot "run-$runId.stop"
    [System.IO.File]::WriteAllText($script:CurrentLogPath, '', [System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $script:CurrentStopSignalPath) {
        Remove-Item -LiteralPath $script:CurrentStopSignalPath -Force
    }
    $script:DisplayedLogLineCount = 0
    $script:StopRequestedAt = $null
    $script:StopWasRequested = $false
    $script:LastExitHandledProcessId = $null
    $logTextBox.Clear()
    $dashboardRecentLog.Clear()
    $logPathText.Text = $script:CurrentLogPath

    try {
        $tokens = Get-AgentArgumentTokens -Mode $mode -CombinedStartStage $combinedStart -TeamRestStart $teamRestStart -LogPath $script:CurrentLogPath -StopSignalPath $script:CurrentStopSignalPath
        $arguments = ($tokens | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '
        $powerShellExe = (Get-Command 'powershell.exe' -ErrorAction Stop).Source
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $powerShellExe
        $startInfo.Arguments = $arguments
        $startInfo.WorkingDirectory = $PSScriptRoot
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $script:AgentProcess = [System.Diagnostics.Process]::Start($startInfo)
        Add-ManagerLogLine "Pokrenuta skripta '$($selected.Name)' (PID $($script:AgentProcess.Id))."
        if ($mode -eq 'Sve') { Add-ManagerLogLine "Pocetna faza: $combinedStart." }
        if ($mode -eq 'OdmoriEkipu') { Add-ManagerLogLine "Pocetna pozicija: $teamRestStart." }
        Set-ManagerState 'Aktivan' 'Running'
        Set-RunButtons $true
    }
    catch {
        Add-ManagerLogLine "Pokretanje nije uspjelo: $($_.Exception.Message)"
        Set-ManagerState 'Greska pri pokretanju' 'Error'
        Set-RunButtons $false
    }
}

function Request-AgentStop {
    if (-not (Test-AgentRunning)) { return }
    try {
        [System.IO.File]::WriteAllText($script:CurrentStopSignalPath, (Get-Date).ToString('O'), [System.Text.UTF8Encoding]::new($false))
        $script:StopRequestedAt = Get-Date
        $script:StopWasRequested = $true
        Add-ManagerLogLine 'Poslan je zahtjev za sigurno zaustavljanje.'
        Set-ManagerState 'Zaustavljanje...' 'Stopping'
        $dashboardStop.IsEnabled = $false
        $scriptsStop.IsEnabled = $false
    }
    catch {
        Add-ManagerLogLine "Zahtjev za zaustavljanje nije zapisan: $($_.Exception.Message)"
    }
}

function Start-HelperScript {
    param([string]$ScriptName)
    $path = Join-Path $PSScriptRoot $ScriptName
    if (-not (Test-Path -LiteralPath $path)) { return }
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-File', $path) -WorkingDirectory $PSScriptRoot
}

$scriptList.Add_SelectionChanged({ Update-SelectedScript })
$dashboardStart.Add_Click({ Start-SelectedAgent })
$scriptsStart.Add_Click({ Start-SelectedAgent })
$dashboardStop.Add_Click({ Request-AgentStop })
$scriptsStop.Add_Click({ Request-AgentStop })

(Find-Control 'NavDashboard').Add_Click({ Set-NavigationPage 0 })
(Find-Control 'NavScripts').Add_Click({ Set-NavigationPage 1 })
(Find-Control 'NavLogs').Add_Click({ Set-NavigationPage 2 })
(Find-Control 'NavSettings').Add_Click({ Set-NavigationPage 3 })
(Find-Control 'QuickScripts').Add_Click({ Set-NavigationPage 1 })
(Find-Control 'QuickLogs').Add_Click({ Set-NavigationPage 2 })
(Find-Control 'QuickAll').Add_Click({
    for ($i = 0; $i -lt $script:ModeCatalog.Count; $i++) {
        if ($script:ModeCatalog[$i].Mode -eq 'Sve') { $scriptList.SelectedIndex = $i; break }
    }
    Set-NavigationPage 1
})
(Find-Control 'OpenLogFolder').Add_Click({ Start-Process -FilePath 'explorer.exe' -ArgumentList @($script:LogsRoot) })
(Find-Control 'ClearLogView').Add_Click({ $logTextBox.Clear(); $dashboardRecentLog.Clear() })
(Find-Control 'ConfigureGemini').Add_Click({ Start-HelperScript 'Postavi Gemini API kljuc.ps1' })
(Find-Control 'TestGemini').Add_Click({ Start-HelperScript 'Testiraj Gemini.ps1' })
(Find-Control 'OpenWorkingFolder').Add_Click({ Start-Process -FilePath 'explorer.exe' -ArgumentList @($PSScriptRoot) })
(Find-Control 'WindowMinimize').Add_Click({ $window.WindowState = [System.Windows.WindowState]::Minimized })
(Find-Control 'WindowMaximize').Add_Click({
    $window.WindowState = if ($window.WindowState -eq [System.Windows.WindowState]::Maximized) {
        [System.Windows.WindowState]::Normal
    }
    else {
        [System.Windows.WindowState]::Maximized
    }
})
(Find-Control 'WindowClose').Add_Click({ $window.Close() })
(Find-Control 'HeaderDragArea').Add_MouseLeftButtonDown({
    if ($_.ClickCount -eq 2) {
        $window.WindowState = if ($window.WindowState -eq [System.Windows.WindowState]::Maximized) {
            [System.Windows.WindowState]::Normal
        }
        else {
            [System.Windows.WindowState]::Maximized
        }
        return
    }
    if ($window.WindowState -eq [System.Windows.WindowState]::Normal) {
        try { $window.DragMove() } catch { }
    }
})

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(500)
$timer.Add_Tick({
    Update-LogViews
    if ($null -ne $script:AgentProcess) {
        try {
            if (-not $script:AgentProcess.HasExited) {
                if ($null -ne $script:StopRequestedAt -and ((Get-Date) - $script:StopRequestedAt).TotalSeconds -ge 8) {
                    Add-ManagerLogLine 'Agent nije odgovorio na stop signal; gasim samo child proces managera.'
                    $script:AgentProcess.Kill()
                    $script:StopRequestedAt = $null
                }
                return
            }
            if ($script:LastExitHandledProcessId -eq $script:AgentProcess.Id) { return }
            $script:LastExitHandledProcessId = $script:AgentProcess.Id
            $exitCode = $script:AgentProcess.ExitCode
            Update-LogViews
            if ($script:StopWasRequested) {
                Set-ManagerState 'Zaustavljeno' 'Ready'
                Add-ManagerLogLine 'Agent je zaustavljen na zahtjev korisnika.'
            }
            elseif ($exitCode -eq 0) {
                Set-ManagerState 'Zavrseno' 'Success'
                Add-ManagerLogLine 'Agent je zavrsio rad.'
            }
            elseif ($exitCode -eq 2) {
                Set-ManagerState 'Zavrseno uz greske' 'Stopping'
                Add-ManagerLogLine 'Sve odabrane faze su obradjene, ali najmanje jedna nije uspjela nakon tri pokusaja.'
            }
            else {
                Set-ManagerState "Greska (kod $exitCode)" 'Error'
                Add-ManagerLogLine "Agent je zavrsio sa kodom greske $exitCode."
            }
            Set-RunButtons $false
            $script:StopRequestedAt = $null
            $script:StopWasRequested = $false
            if ($script:CloseRequested) {
                $script:CloseRequested = $false
                $window.Close()
            }
        }
        catch { }
    }
})

$window.Add_Closing({
    if (Test-AgentRunning) {
        if (-not $script:CloseRequested) {
            $answer = [System.Windows.MessageBox]::Show(
                'Agent jos radi. Poslati zahtjev za zaustavljanje i zatvoriti manager?',
                'AI Agent Manager',
                [System.Windows.MessageBoxButton]::YesNo,
                [System.Windows.MessageBoxImage]::Question
            )
            if ($answer -ne [System.Windows.MessageBoxResult]::Yes) {
                $_.Cancel = $true
                return
            }
            $script:CloseRequested = $true
            Request-AgentStop
        }
        if (Test-AgentRunning) {
            $_.Cancel = $true
            return
        }
    }
    $timer.Stop()
})

Update-SelectedScript
Set-NavigationPage 0
Set-ManagerState 'Spreman' 'Ready'
Set-RunButtons $false
$timer.Start()
[void]$window.ShowDialog()
