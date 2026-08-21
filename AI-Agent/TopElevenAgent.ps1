param(
    [switch]$SelfTest,
    [switch]$DryRun,
    [switch]$Calibration,
    [ValidateSet('Zeleni', 'OdmoriEkipu', 'TV', 'Mourinho', 'Kampus', 'PutSaveza', 'TreningIgraca', 'Sve')]
    [string]$Mode = 'Zeleni',
    [ValidateSet('GK', 'DL', 'DC1', 'DC2', 'DR', 'DMC', 'MC1', 'MC2', 'AML', 'AMR', 'ST', 'DL_2', 'ST_2', 'AMR_2', 'AML_2')]
    [string]$TeamRestStart = 'GK',
    [ValidateSet('Mourinho', 'TV', 'PutSaveza', 'Kampus', 'Zeleni')]
    [string]$CombinedStartStage = 'Mourinho',
    [switch]$AutoStart,
    [switch]$ExitAfterRun,
    [string]$LogPath = '',
    [string]$StopSignalPath = ''
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class Win32Agent {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int command);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte virtualKey, byte scanCode, uint flags, UIntPtr extraInfo);
    [DllImport("user32.dll")]
    public static extern IntPtr GetDC(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
    [DllImport("gdi32.dll")]
    public static extern uint GetPixel(IntPtr hDC, int x, int y);
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();

    public static IntPtr FindVisibleWindow(string titlePrefix) {
        IntPtr found = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr ignored) {
            if (!IsWindowVisible(hWnd)) return true;
            StringBuilder title = new StringBuilder(512);
            GetWindowText(hWnd, title, title.Capacity);
            if (title.ToString().StartsWith(titlePrefix, StringComparison.OrdinalIgnoreCase)) {
                found = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static IntPtr[] FindVisibleWindows(string titlePrefix) {
        System.Collections.Generic.List<IntPtr> found = new System.Collections.Generic.List<IntPtr>();
        EnumWindows(delegate(IntPtr hWnd, IntPtr ignored) {
            if (!IsWindowVisible(hWnd)) return true;
            StringBuilder title = new StringBuilder(512);
            GetWindowText(hWnd, title, title.Capacity);
            if (title.ToString().StartsWith(titlePrefix, StringComparison.OrdinalIgnoreCase)) {
                found.Add(hWnd);
            }
            return true;
        }, IntPtr.Zero);
        return found.ToArray();
    }

    public static string GetWindowTitle(IntPtr hWnd) {
        StringBuilder title = new StringBuilder(512);
        GetWindowText(hWnd, title, title.Capacity);
        return title.ToString();
    }
}
'@

[Win32Agent]::SetProcessDPIAware() | Out-Null

$script:BlueStacksExe = 'C:\Program Files\BlueStacks_nxt\HD-Player.exe'
$script:BlueStacksInstance = 'Pie64'
$script:TopElevenPackage = 'eu.nordeus.topeleven.android'
$script:WindowTitle = 'BlueStacks App Player'
$script:BlueStacksConfigPath = 'C:\ProgramData\BlueStacks_nxt\bluestacks.conf'
$script:BlueStacksInstanceDisplayName = $null
$script:TopElevenShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Top Eleven.lnk'
$script:PythonExe = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script:XDetectorScript = Join-Path $PSScriptRoot 'XDetector.py'
$script:VisionAgentScript = Join-Path $PSScriptRoot 'VisionAgent.py'
$script:VisionConfigPath = Join-Path $PSScriptRoot 'ai_config.json'
$script:VisionAgentProcess = $null
$script:VisionEnabled = $true
$script:VisionAnalysisIntervalMs = 2500
$script:VisionAiOnlyFallbackAfterSeconds = 60
$script:VisionAiProbeIntervalSeconds = 20.5
$script:AdControlsAiOnly = $true
$script:LastGooglePlayClickAt = $null
$script:VisionRetryAfterErrorSeconds = 16
$script:VisionUnavailableUntil = [datetime]::MinValue
$script:VisionMalformedJsonRetryActive = $false
$script:VisionCacheByState = @{}
$script:AiTopElevenReturned = $false
$script:AiAdVisible = $false
$script:ConnectionPopupLastCheckAt = [datetime]::MinValue
$script:ConnectionPopupRecoveryActive = $false
$script:BlueStacksPlayerLog = 'C:\ProgramData\BlueStacks_nxt\Logs\Player.log'
$script:ConfigPath = Join-Path $PSScriptRoot 'config.json'
$script:Config = $null
$script:ForegroundStateCache = $null
$script:ForegroundStateCheckedAt = $null
$script:LastHandledGooglePlayEvent = $null
$script:LastGooglePlayBackAt = $null
$script:GooglePlayRestoreKey = $null
$script:GooglePlayBackAttemptCount = 0
$script:PlayDestinationCheckedAt = $null
$script:PlayDestinationCache = $false
$script:DetectedPlayDestinationCloseX = $null
$script:DetectedPlayDestinationCloseY = $null
$script:DetectedFreeButtonX = $null
$script:DetectedFreeButtonY = $null
$script:FreeButtonStableCount = 0
$script:FreeButtonStableSince = $null
$script:Mode = $Mode
$script:TeamRestStartKey = $TeamRestStart
$script:CombinedStartStage = $CombinedStartStage
$script:ExternalLogPath = $LogPath
$script:StopSignalPath = $StopSignalPath
$script:AutoStart = [bool]$AutoStart
$script:ExitAfterRun = [bool]$ExitAfterRun
$script:TeamRestQueue = @(
    [PSCustomObject]@{ Key = 'GK';    Display = 'GK';                  Label = 'GK';             View = 'Top';    Y = 0.256 },
    [PSCustomObject]@{ Key = 'DL';    Display = 'DL';                  Label = 'DL';             View = 'Top';    Y = 0.336 },
    [PSCustomObject]@{ Key = 'DC1';   Display = 'DC 1';                Label = 'DC 1';           View = 'Top';    Y = 0.417 },
    [PSCustomObject]@{ Key = 'DC2';   Display = 'DC 2';                Label = 'DC 2';           View = 'Top';    Y = 0.497 },
    [PSCustomObject]@{ Key = 'DR';    Display = 'DR';                  Label = 'DR';             View = 'Top';    Y = 0.576 },
    [PSCustomObject]@{ Key = 'DMC';   Display = 'DMC';                 Label = 'DMC';            View = 'Top';    Y = 0.656 },
    [PSCustomObject]@{ Key = 'MC1';   Display = 'MC 1';                Label = 'MC 1';           View = 'Top';    Y = 0.736 },
    [PSCustomObject]@{ Key = 'MC2';   Display = 'MC 2';                Label = 'MC 2';           View = 'Bottom'; Y = 0.256 },
    [PSCustomObject]@{ Key = 'AML';   Display = 'AML';                 Label = 'AML';            View = 'Bottom'; Y = 0.336 },
    [PSCustomObject]@{ Key = 'AMR';   Display = 'AMR';                 Label = 'AMR';            View = 'Bottom'; Y = 0.417 },
    [PSCustomObject]@{ Key = 'ST';    Display = 'ST';                  Label = 'ST';             View = 'Bottom'; Y = 0.497 },
    [PSCustomObject]@{ Key = 'DL_2';  Display = 'DL (drugi krug)';     Label = 'DL - ponovo';    View = 'Top';    Y = 0.336 },
    [PSCustomObject]@{ Key = 'ST_2';  Display = 'ST (drugi krug)';     Label = 'ST - ponovo';    View = 'Bottom'; Y = 0.497 },
    [PSCustomObject]@{ Key = 'AMR_2'; Display = 'AMR (drugi krug)';    Label = 'AMR - ponovo';   View = 'Bottom'; Y = 0.417 },
    [PSCustomObject]@{ Key = 'AML_2'; Display = 'AML (drugi krug)';    Label = 'AML - ponovo';   View = 'Bottom'; Y = 0.336 }
)
$script:Cancelled = $false
$script:Running = $false
$script:RunFailed = $false
$script:HadStageFailures = $false
$script:ShortTransitionBufferMs = 500
$script:TransitionBufferMs = 1800
$script:LongTransitionBufferMs = 3000
$script:AdWaitSeconds = 60
$script:XDetectionDelaySeconds = 5
$script:ScrollSteps = 6
$script:TVClickBufferMs = 1500
$script:TVNavigationBufferMs = 2000
$script:TVWatchButtonWaitSeconds = 30
$script:CampusHundredButtonWaitSeconds = 180
$script:CampusOpenBufferMs = 3000
$script:CampusBuildingClickAttempts = 3
$script:CampusDetailOpenWaitSeconds = 8
$script:PutSavezaAdButtonWaitSeconds = 30
$script:PutSavezaMenuScrollAttempts = 10
$script:PutSavezaMenuScrollSteps = 2
$script:StageRetryAttempts = 3
$script:StageRecoveryLaunchTimeoutSeconds = 90
$script:StagePreflightRecoveryRequired = $false
$script:TrainingPlayerClickBufferMs = 1800
$script:TrainingPlayerCloseBufferMs = 1500
$script:ConnectionRecoveryWaitMs = 12000
$script:AdWakeTapAfterSeconds = 75
$script:AdWakeTapIntervalSeconds = 12
$script:AdWakeBurstSeconds = 6
$script:AdWakeTapMaximum = 20

if (Test-Path -LiteralPath $script:ConfigPath) {
    try {
        $script:Config = Get-Content -Raw -LiteralPath $script:ConfigPath | ConvertFrom-Json
        if ($script:Config.windowTitle) { $script:WindowTitle = [string]$script:Config.windowTitle }
        if ($null -ne $script:Config.transitionMs.short) { $script:ShortTransitionBufferMs = [int]$script:Config.transitionMs.short }
        if ($null -ne $script:Config.transitionMs.normal) { $script:TransitionBufferMs = [int]$script:Config.transitionMs.normal }
        if ($null -ne $script:Config.transitionMs.long) { $script:LongTransitionBufferMs = [int]$script:Config.transitionMs.long }
        if ($null -ne $script:Config.adWaitSeconds) { $script:AdWaitSeconds = [int]$script:Config.adWaitSeconds }
        if ($null -ne $script:Config.xDetectionDelaySeconds) { $script:XDetectionDelaySeconds = [int]$script:Config.xDetectionDelaySeconds }
        if ($null -ne $script:Config.scrollSteps) { $script:ScrollSteps = [int]$script:Config.scrollSteps }
        if ($null -ne $script:Config.tvClickBufferMs) { $script:TVClickBufferMs = [int]$script:Config.tvClickBufferMs }
        if ($null -ne $script:Config.tvNavigationBufferMs) { $script:TVNavigationBufferMs = [int]$script:Config.tvNavigationBufferMs }
        if ($null -ne $script:Config.tvWatchButtonWaitSeconds) { $script:TVWatchButtonWaitSeconds = [int]$script:Config.tvWatchButtonWaitSeconds }
        if ($null -ne $script:Config.campusHundredButtonWaitSeconds) { $script:CampusHundredButtonWaitSeconds = [int]$script:Config.campusHundredButtonWaitSeconds }
        if ($null -ne $script:Config.campusOpenBufferMs) { $script:CampusOpenBufferMs = [int]$script:Config.campusOpenBufferMs }
        if ($null -ne $script:Config.campusBuildingClickAttempts) { $script:CampusBuildingClickAttempts = [int]$script:Config.campusBuildingClickAttempts }
        if ($null -ne $script:Config.campusDetailOpenWaitSeconds) { $script:CampusDetailOpenWaitSeconds = [int]$script:Config.campusDetailOpenWaitSeconds }
        if ($null -ne $script:Config.putSavezaAdButtonWaitSeconds) { $script:PutSavezaAdButtonWaitSeconds = [int]$script:Config.putSavezaAdButtonWaitSeconds }
        if ($null -ne $script:Config.putSavezaMenuScrollAttempts) { $script:PutSavezaMenuScrollAttempts = [int]$script:Config.putSavezaMenuScrollAttempts }
        if ($null -ne $script:Config.putSavezaMenuScrollSteps) { $script:PutSavezaMenuScrollSteps = [int]$script:Config.putSavezaMenuScrollSteps }
        if ($null -ne $script:Config.stageRetryAttempts) { $script:StageRetryAttempts = [Math]::Max(1, [int]$script:Config.stageRetryAttempts) }
        if ($null -ne $script:Config.stageRecoveryLaunchTimeoutSeconds) { $script:StageRecoveryLaunchTimeoutSeconds = [Math]::Max(20, [int]$script:Config.stageRecoveryLaunchTimeoutSeconds) }
        if ($null -ne $script:Config.trainingPlayerClickBufferMs) { $script:TrainingPlayerClickBufferMs = [int]$script:Config.trainingPlayerClickBufferMs }
        if ($null -ne $script:Config.trainingPlayerCloseBufferMs) { $script:TrainingPlayerCloseBufferMs = [int]$script:Config.trainingPlayerCloseBufferMs }
        if ($null -ne $script:Config.connectionRecoveryWaitMs) { $script:ConnectionRecoveryWaitMs = [int]$script:Config.connectionRecoveryWaitMs }
        if ($null -ne $script:Config.adWakeTapAfterSeconds) { $script:AdWakeTapAfterSeconds = [int]$script:Config.adWakeTapAfterSeconds }
        if ($null -ne $script:Config.adWakeTapIntervalSeconds) { $script:AdWakeTapIntervalSeconds = [int]$script:Config.adWakeTapIntervalSeconds }
        if ($null -ne $script:Config.adWakeBurstSeconds) { $script:AdWakeBurstSeconds = [int]$script:Config.adWakeBurstSeconds }
        if ($null -ne $script:Config.adWakeTapMaximum) { $script:AdWakeTapMaximum = [int]$script:Config.adWakeTapMaximum }
    }
    catch {
        throw "Neispravan config.json: $($_.Exception.Message)"
    }
}

$script:DryRun = [bool]($DryRun -or $Calibration)
$script:Calibration = [bool]$Calibration

if (Test-Path -LiteralPath $script:VisionConfigPath) {
    $visionConfig = Get-Content -Raw -LiteralPath $script:VisionConfigPath | ConvertFrom-Json
    if ($null -ne $visionConfig.enabled) { $script:VisionEnabled = [bool]$visionConfig.enabled }
    if ($null -ne $visionConfig.analysisIntervalMs) { $script:VisionAnalysisIntervalMs = [int]$visionConfig.analysisIntervalMs }
    if ($null -ne $visionConfig.aiOnlyFallbackAfterSeconds) { $script:VisionAiOnlyFallbackAfterSeconds = [int]$visionConfig.aiOnlyFallbackAfterSeconds }
    if ($null -ne $visionConfig.aiProbeIntervalSeconds) { $script:VisionAiProbeIntervalSeconds = [double]$visionConfig.aiProbeIntervalSeconds }
    if ($null -ne $visionConfig.retryAfterErrorSeconds) { $script:VisionRetryAfterErrorSeconds = [int]$visionConfig.retryAfterErrorSeconds }
}

function Add-Log {
    param([string]$Text)
    $stamp = Get-Date -Format 'HH:mm:ss'
    $line = "[$stamp] $Text"
    $log.AppendText("$line`r`n")
    $log.SelectionStart = $log.TextLength
    $log.ScrollToCaret()
    if (-not [string]::IsNullOrWhiteSpace($script:ExternalLogPath)) {
        try {
            $logDirectory = Split-Path -Parent $script:ExternalLogPath
            if (-not [string]::IsNullOrWhiteSpace($logDirectory) -and -not (Test-Path -LiteralPath $logDirectory)) {
                New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
            }
            Add-Content -LiteralPath $script:ExternalLogPath -Value $line -Encoding UTF8
        }
        catch {
            # Vanjski manager log je samo prikaz; automatizacija ne smije pasti zbog njega.
        }
    }
    [System.Windows.Forms.Application]::DoEvents()
}

function Set-Status {
    param([string]$Text, [System.Drawing.Color]$Color = [System.Drawing.Color]::FromArgb(220, 235, 255))
    $status.Text = $Text
    $status.ForeColor = $Color
    Add-Log $Text
}

function Test-Cancelled {
    [System.Windows.Forms.Application]::DoEvents()
    if (-not [string]::IsNullOrWhiteSpace($script:StopSignalPath) -and
        (Test-Path -LiteralPath $script:StopSignalPath)) {
        $script:Cancelled = $true
    }
    if ($script:Cancelled) { throw [System.OperationCanceledException]::new('Zaustavljeno od korisnika.') }
}

function Wait-Agent {
    param([int]$Milliseconds)
    $remaining = $Milliseconds
    while ($remaining -gt 0) {
        Test-Cancelled
        $slice = [Math]::Min(20, $remaining)
        Start-Sleep -Milliseconds $slice
        $remaining -= $slice
    }
}

function Get-BlueStacksInstanceDisplayName {
    if (-not [string]::IsNullOrWhiteSpace($script:BlueStacksInstanceDisplayName)) {
        return $script:BlueStacksInstanceDisplayName
    }
    if (-not (Test-Path -LiteralPath $script:BlueStacksConfigPath)) { return $null }

    try {
        $escapedInstance = [regex]::Escape($script:BlueStacksInstance)
        $displayNamePattern = '^bst\.instance\.' + $escapedInstance + '\.display_name="(?<name>[^"]+)"'
        foreach ($line in Get-Content -LiteralPath $script:BlueStacksConfigPath -ErrorAction Stop) {
            if ($line -match $displayNamePattern) {
                $script:BlueStacksInstanceDisplayName = [string]$Matches.name
                return $script:BlueStacksInstanceDisplayName
            }
        }
    }
    catch { }
    return $null
}

function Get-BlueStacksWindow {
    param([switch]$RequireConfiguredInstance)

    $windows = @([Win32Agent]::FindVisibleWindows($script:WindowTitle) | Where-Object { $_ -ne [IntPtr]::Zero })
    if ($windows.Count -eq 0) { return [IntPtr]::Zero }
    if ($windows.Count -eq 1 -and -not $RequireConfiguredInstance) { return [IntPtr]$windows[0] }

    # Kod vise BlueStacks prozora biramo iskljucivo proces pokrenut za
    # konfiguriranu instancu. Time recovery nikad ne ugasi tudju instancu samo
    # zato sto joj naslov takodjer pocinje sa "BlueStacks App Player".
    $configuredDisplayName = Get-BlueStacksInstanceDisplayName
    if (-not [string]::IsNullOrWhiteSpace($configuredDisplayName)) {
        $titleMatches = @($windows | Where-Object {
            [Win32Agent]::GetWindowTitle([IntPtr]$_) -eq $configuredDisplayName
        })
        if ($titleMatches.Count -eq 1) { return [IntPtr]$titleMatches[0] }
    }

    # CommandLine je dodatna provjera za instalacije na kojima display_name nije
    # upisan. Tihi CIM failure nije fatalan jer se iznad koristi lokalni
    # BlueStacks config; ako ni jedan dokaz nije dostupan, funkcija fail-closed.
    $instancePattern = '(?i)--instance(?:=|\s+)"?' + [regex]::Escape($script:BlueStacksInstance) + '(?:"|\s|$)'
    $matchingWindows = New-Object System.Collections.Generic.List[System.IntPtr]
    foreach ($candidateHandle in $windows) {
        [uint32]$candidateProcessId = 0
        [Win32Agent]::GetWindowThreadProcessId([IntPtr]$candidateHandle, [ref]$candidateProcessId) | Out-Null
        if ($candidateProcessId -le 0) { continue }
        try {
            $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $candidateProcessId" -ErrorAction Stop
            if ($null -ne $processInfo -and [string]$processInfo.CommandLine -match $instancePattern) {
                $matchingWindows.Add([IntPtr]$candidateHandle)
            }
        }
        catch { }
    }
    if ($matchingWindows.Count -eq 1) { return [IntPtr]$matchingWindows[0] }

    # Fail-closed: dvosmislen prozor se ne smije koristiti za klik niti force quit.
    return [IntPtr]::Zero
}

function Wait-ForCondition {
    param(
        [string]$Description,
        [int]$TimeoutSeconds,
        [scriptblock]$Condition
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 50
    }
    throw "Isteklo je vrijeme cekanja: $Description"
}

function Get-WindowRectangle {
    param([IntPtr]$Handle)
    $rect = New-Object Win32Agent+RECT
    if (-not [Win32Agent]::GetWindowRect($Handle, [ref]$rect)) {
        throw 'Nije moguce ocitati velicinu BlueStacks prozora.'
    }
    return $rect
}

function Get-GameViewportRectangle {
    param([IntPtr]$Handle)

    $rect = Get-WindowRectangle $Handle
    $referenceDpi = 96.0
    $titleBarPx = 40.0
    $rightToolbarPx = 42.0
    if ($null -ne $script:Config) {
        if ($script:Config.referenceWindowsDpi) { $referenceDpi = [double]$script:Config.referenceWindowsDpi }
        if ($null -ne $script:Config.titleBarPx) { $titleBarPx = [double]$script:Config.titleBarPx }
        if ($null -ne $script:Config.rightToolbarPx) { $rightToolbarPx = [double]$script:Config.rightToolbarPx }
    }

    $graphics = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
    try { $dpiScale = $graphics.DpiX / $referenceDpi }
    finally { $graphics.Dispose() }

    $viewport = [pscustomobject]@{
        Left = $rect.Left
        Top = $rect.Top + [int][Math]::Round($titleBarPx * $dpiScale)
        Right = $rect.Right - [int][Math]::Round($rightToolbarPx * $dpiScale)
        Bottom = $rect.Bottom
    }
    if ($viewport.Right -le $viewport.Left -or $viewport.Bottom -le $viewport.Top) {
        throw 'Konfiguracija daje neispravan game viewport.'
    }
    return $viewport
}

function Click-Relative {
    param(
        [IntPtr]$Handle,
        [double]$X,
        [double]$Y,
        [string]$Name
    )
    $rect = Get-WindowRectangle $Handle
    $screenX = [int]($rect.Left + (($rect.Right - $rect.Left) * $X))
    $screenY = [int]($rect.Top + (($rect.Bottom - $rect.Top) * $Y))
    if ($script:DryRun) {
        Add-Log "DRY RUN klik: $Name ($screenX, $screenY)"
        return
    }
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 30
    [Win32Agent]::SetCursorPos($screenX, $screenY) | Out-Null
    [Win32Agent]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Add-Log "Klik: $Name ($screenX, $screenY)"
}

function Click-GameRelative {
    param(
        [IntPtr]$Handle,
        [double]$X,
        [double]$Y,
        [string]$Name
    )
    $rect = Get-GameViewportRectangle $Handle
    $gameLeft = $rect.Left
    $gameTop = $rect.Top
    $gameRight = $rect.Right
    $gameBottom = $rect.Bottom
    $screenX = [int]($gameLeft + (($gameRight - $gameLeft) * $X))
    $screenY = [int]($gameTop + (($gameBottom - $gameTop) * $Y))
    if ($script:DryRun) {
        Add-Log "DRY RUN klik u igri: $Name ($screenX, $screenY)"
        return
    }
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 30
    [Win32Agent]::SetCursorPos($screenX, $screenY) | Out-Null
    [Win32Agent]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Add-Log "Klik u igri: $Name ($screenX, $screenY)"
}

function Send-Escape {
    param([IntPtr]$Handle)
    if ($script:DryRun) { Add-Log 'DRY RUN: Back / Escape'; return }
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 30
    [Win32Agent]::keybd_event(0x1B, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::keybd_event(0x1B, 0, 0x0002, [UIntPtr]::Zero)
    Add-Log 'Pokusaj zatvaranja popupa: Back / Escape'
}

function Send-BlueStacksBack {
    param([IntPtr]$Handle)
    if ($script:DryRun) { Add-Log 'DRY RUN: BlueStacks Back'; return }
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 50
    # Escape je Android Back u BlueStacksu, pa nema zavisnosti od koordinata.
    [Win32Agent]::keybd_event(0x1B, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::keybd_event(0x1B, 0, 0x0002, [UIntPtr]::Zero)
    Add-Log 'BlueStacks Back poslan preko Escape tipke.'
}

function Get-BlueStacksForegroundState {
    $now = Get-Date
    if ($null -ne $script:ForegroundStateCheckedAt -and
        ($now - $script:ForegroundStateCheckedAt).TotalMilliseconds -lt 250) {
        return $script:ForegroundStateCache
    }

    $script:ForegroundStateCheckedAt = $now
    $state = $null
    try {
        if (Test-Path -LiteralPath $script:BlueStacksPlayerLog) {
            $lines = @(Get-Content -LiteralPath $script:BlueStacksPlayerLog -Tail 400 -ErrorAction Stop)
            for ($index = $lines.Count - 1; $index -ge 0; $index--) {
                $line = [string]$lines[$index]
                if ($line -match 'hcallOnActivityDisplayedClbk\s*:\s*package\s*=\s*(?<Package>[^\s]+)\s+activity\s*=\s*(?<Activity>[^\s]+)') {
                    $eventTime = $null
                    if ($line.Length -ge 28) {
                        $parsedTime = [DateTimeOffset]::MinValue
                        if ([DateTimeOffset]::TryParse($line.Substring(0, 28), [ref]$parsedTime)) {
                            $eventTime = $parsedTime.LocalDateTime
                        }
                    }
                    $state = [PSCustomObject]@{
                        Package = [string]$Matches.Package
                        Activity = [string]$Matches.Activity
                        Signature = $line
                        EventTime = $eventTime
                    }
                    break
                }
            }
        }
    }
    catch {
        # Player.log je samo dodatna sigurnosna provjera; cekanje X-a i dalje radi.
    }

    $script:ForegroundStateCache = $state
    return $state
}

function Get-RecentGooglePlayLinkEvent {
    param([datetime]$AdStartedAt)

    try {
        if (-not (Test-Path -LiteralPath $script:BlueStacksPlayerLog)) { return $null }
        $lines = @(Get-Content -LiteralPath $script:BlueStacksPlayerLog -Tail 500 -ErrorAction Stop)
        for ($index = $lines.Count - 1; $index -ge 0; $index--) {
            $line = [string]$lines[$index]
            if ($line -notmatch 'hcallOnActivityDisplayedClbk\s*:\s*package\s*=\s*(?<Package>com\.android\.(?:vending|chrome))') {
                continue
            }
            $eventTime = $null
            if ($line.Length -ge 28) {
                $parsedTime = [DateTimeOffset]::MinValue
                if ([DateTimeOffset]::TryParse($line.Substring(0, 28), [ref]$parsedTime)) {
                    $eventTime = $parsedTime.LocalDateTime
                }
            }
            if ($null -ne $eventTime -and $eventTime -lt $AdStartedAt.AddSeconds(-2)) {
                return $null
            }
            return [PSCustomObject]@{
                Package = [string]$Matches.Package
                Signature = $line
                EventTime = $eventTime
            }
        }
    }
    catch { }
    return $null
}

function Restore-AdFromGooglePlay {
    param(
        [IntPtr]$Handle,
        [datetime]$AdStartedAt
    )

    $state = Get-BlueStacksForegroundState
    $externalEventSignature = if ($null -ne $state -and
        ($state.Package -eq 'com.android.vending' -or $state.Package -eq 'com.android.chrome')) {
        [string]$state.Signature
    }
    else { $null }
    $externalByPackage = $null -ne $state -and
        ($state.Package -eq 'com.android.vending' -or $state.Package -eq 'com.android.chrome') -and
        $null -ne $state.EventTime -and
        $state.EventTime -ge $AdStartedAt.AddSeconds(-2) -and
        $state.Signature -ne $script:LastHandledGooglePlayEvent
    $recentAiPlayClick = $null -ne $script:LastGooglePlayClickAt -and
        ((Get-Date) - $script:LastGooglePlayClickAt).TotalSeconds -le 15
    $externalByAi = $null
    if (-not $externalByPackage -and $recentAiPlayClick) {
        $externalByAi = Test-AiExternalNavigationVisible $Handle $AdStartedAt
    }
    if (-not $externalByPackage -and $externalByAi -ne $true) { return $false }
    $externalWasAiOnly = -not $externalByPackage -and $externalByAi -eq $true

    $clickKey = if ($null -ne $script:LastGooglePlayClickAt) {
        [string]$script:LastGooglePlayClickAt.Ticks
    }
    else { 'automatic' }
    $restoreKey = "{0}:{1}" -f $AdStartedAt.Ticks, $clickKey
    if ($script:GooglePlayRestoreKey -ne $restoreKey) {
        $script:GooglePlayRestoreKey = $restoreKey
        $script:GooglePlayBackAttemptCount = 0
        $script:LastGooglePlayBackAt = $null
    }

    $destination = if ($null -ne $state -and $state.Package -eq 'com.android.chrome') {
        'play.google/Chrome'
    }
    else { 'Google Play Store' }

    # Ne salji vise Back komandi u brzom nizu. Nakon prve, svaka naredna
    # zahtijeva novu AI potvrdu da je Store/Chrome zaista jos na ekranu.
    if ($null -ne $script:LastGooglePlayBackAt -and
        ((Get-Date) - $script:LastGooglePlayBackAt).TotalMilliseconds -lt 1600) {
        return $true
    }
    if ($script:GooglePlayBackAttemptCount -ge 3) {
        Set-Status "$destination je i dalje otvoren nakon 3 potvrdena Back pokusaja." ([System.Drawing.Color]::FromArgb(255, 150, 100))
        return $true
    }
    if ($script:GooglePlayBackAttemptCount -gt 0) {
        $aiBeforeAnotherBack = Test-AiExternalNavigationVisible $Handle $AdStartedAt -ForceRefresh
        if ($aiBeforeAnotherBack -eq $false) {
            if ($null -ne $externalEventSignature) {
                $script:LastHandledGooglePlayEvent = $externalEventSignature
            }
            $script:LastGooglePlayClickAt = $null
            $script:GooglePlayRestoreKey = $null
            $script:GooglePlayBackAttemptCount = 0
            Add-Log 'AI vise ne vidi Google Play/Chrome; dodatni Back nije poslan.'
            return $true
        }
        if ($null -eq $aiBeforeAnotherBack) {
            Add-Log 'AI nije potvrdio da je Store jos otvoren; cekam bez dodatnog Back klika.'
            return $true
        }
    }

    $script:GooglePlayBackAttemptCount++
    $backAttempt = $script:GooglePlayBackAttemptCount
    Set-Status "Otvoren je $destination - saljem Back ($backAttempt/3)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
    Send-BlueStacksBack $Handle
    $script:LastGooglePlayBackAt = Get-Date
    Wait-Agent 900

    $script:ForegroundStateCheckedAt = $null
    $state = Get-BlueStacksForegroundState
    $externalByPackage = $null -ne $state -and
        ($state.Package -eq 'com.android.vending' -or $state.Package -eq 'com.android.chrome')
    if (-not $externalByPackage) {
        # Ako package signal nije dostupan, ne pretpostavljaj da je Back uspio.
        # Nova AI slika prvo provjerava je li Store/Chrome jos uvijek vidljiv.
        if ($externalWasAiOnly -or $null -eq $state -or [string]::IsNullOrWhiteSpace([string]$state.Package)) {
            $aiAfterBack = Test-AiExternalNavigationVisible $Handle $AdStartedAt -ForceRefresh
            if ($aiAfterBack -eq $true) {
                Add-Log 'AI i dalje vidi Google Play/Chrome nakon Back-a; ostajem u sigurnom restore toku.'
                return $true
            }
            if ($null -eq $aiAfterBack) {
                Add-Log 'Nema svjezeg package ni AI signala nakon Back-a; cekam novu provjeru bez klika po ekranu.'
                return $true
            }
        }
        $script:LastGooglePlayClickAt = $null
        if ($null -ne $externalEventSignature) {
            $script:LastHandledGooglePlayEvent = $externalEventSignature
        }
        $script:GooglePlayRestoreKey = $null
        $script:GooglePlayBackAttemptCount = 0
        Add-Log 'Google Play/Chrome vise nije foreground; reklamni tok sada potvrduje trenutni ekran.'
        return $true
    }

    # Ako Player.log jos pokazuje Store, sljedeci Back se ne salje dok AI na
    # novoj slici opet ne potvrdi da je vanjska destinacija stvarno otvorena.
    $aiStillExternal = Test-AiExternalNavigationVisible $Handle $AdStartedAt -ForceRefresh
    if ($aiStillExternal -eq $false) {
        $script:LastHandledGooglePlayEvent = [string]$state.Signature
        $script:LastGooglePlayClickAt = $null
        $script:GooglePlayRestoreKey = $null
        $script:GooglePlayBackAttemptCount = 0
        Add-Log 'AI vise ne vidi Google Play/Chrome; povratak u reklamni tok je potvrden.'
    }
    return $true
}

function Wait-ForAdXAfterGooglePlayReturn {
    param(
        [IntPtr]$Handle,
        [datetime]$Deadline,
        [datetime]$AdStartedAt,
        [string]$Label
    )

    Set-Status "Vracen sam iz Google Play Storea; nastavljam cekati pravi X za $Label..."
    $nextAiProbeAt = Get-Date
    $expectedState = "ad_control_ai_only_after_play_$($AdStartedAt.Ticks)"
    while ((Get-Date) -lt $Deadline) {
        Test-Cancelled
        if (Restore-AdFromGooglePlay $Handle $AdStartedAt) {
            Start-Sleep -Milliseconds 100
            continue
        }
        if ((Get-Date) -ge $nextAiProbeAt) {
            $nextAiProbeAt = (Get-Date).AddSeconds($script:VisionAiProbeIntervalSeconds)
            Add-Log "AI provjera kontrole nakon povratka iz Storea za $Label..."
            $aiControlReady = Test-AiOnlyAdControlReady $Handle $expectedState
            if ($script:AiTopElevenReturned) {
                Add-Log "AI je potvrdio da je $Label vec zatvorena nakon povratka iz Storea."
                return $false
            }
            if ($aiControlReady) {
                if ($script:DetectedAdCloseKind -eq 'skip') {
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY '>> - AI nastavi reklamu'
                    Wait-Agent $script:TransitionBufferMs
                    $expectedState = "ad_control_ai_only_after_play_$((Get-Date).Ticks)"
                    $nextAiProbeAt = Get-Date
                    continue
                }
                if ($script:DetectedAdCloseKind -eq 'google_play') {
                    $script:LastGooglePlayClickAt = Get-Date
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY 'Google Play - AI'
                    Wait-Agent 1500
                    Restore-AdFromGooglePlay $Handle $AdStartedAt | Out-Null
                    $expectedState = "ad_control_ai_only_after_play_$((Get-Date).Ticks)"
                    $nextAiProbeAt = Get-Date
                    continue
                }
                return $true
            }
        }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

function Get-ColorMatchCount {
    param(
        [IntPtr]$Handle,
        [double]$Left,
        [double]$Top,
        [double]$Right,
        [double]$Bottom,
        [scriptblock]$ColorTest,
        [ValidateSet('Game', 'Window')]
        [string]$Viewport = 'Game'
    )
    $rect = if ($Viewport -eq 'Game') { Get-GameViewportRectangle $Handle } else { Get-WindowRectangle $Handle }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $dc = [Win32Agent]::GetDC([IntPtr]::Zero)
    $matches = 0
    try {
        for ($gx = 0; $gx -lt 32; $gx++) {
            for ($gy = 0; $gy -lt 12; $gy++) {
                $x = [int]($rect.Left + $width * ($Left + (($Right - $Left) * $gx / 31)))
                $y = [int]($rect.Top + $height * ($Top + (($Bottom - $Top) * $gy / 11)))
                $pixel = [Win32Agent]::GetPixel($dc, $x, $y)
                $r = [int]($pixel -band 0xFF)
                $g = [int](($pixel -shr 8) -band 0xFF)
                $b = [int](($pixel -shr 16) -band 0xFF)
                if (& $ColorTest $r $g $b) { $matches++ }
            }
        }
    }
    finally {
        [Win32Agent]::ReleaseDC([IntPtr]::Zero, $dc) | Out-Null
    }
    return $matches
}

function Test-GameHomeLoaded {
    param([IntPtr]$Handle)
    $greenCount = Get-ColorMatchCount $Handle 0.075 0.045 0.19 0.105 {
        param($r, $g, $b)
        $g -gt 125 -and $g -gt ($r * 1.25) -and $g -gt ($b * 1.20)
    }
    return $greenCount -ge 5
}

function Get-TeamRestFreeButtonSnapshot {
    param([IntPtr]$Handle)
    Start-XDetector
    if ($script:XDetectorProcess.HasExited) {
        $details = $script:XDetectorProcess.StandardError.ReadToEnd()
        throw "Recognizer teksta BESPLATNO se neocekivano zatvorio. $details"
    }
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'team_rest_free_button'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    $line = $script:XDetectorProcess.StandardOutput.ReadLine()
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw 'Recognizer teksta BESPLATNO nije vratio rezultat.'
    }
    return ($line | ConvertFrom-Json)
}

function Test-FreeButtonReady {
    param([IntPtr]$Handle)
    if ($script:Mode -eq 'OdmoriEkipu') {
        $result = Get-TeamRestFreeButtonSnapshot $Handle
        if (-not [bool]$result.ready) {
            $script:DetectedFreeButtonX = $null
            $script:DetectedFreeButtonY = $null
            $script:FreeButtonStableCount = 0
            $script:FreeButtonStableSince = $null
            return $false
        }

        $x = [double]$result.x
        $y = [double]$result.y
        $sameButton = $null -ne $script:DetectedFreeButtonX -and
            [Math]::Abs($x - $script:DetectedFreeButtonX) -le 0.01 -and
            [Math]::Abs($y - $script:DetectedFreeButtonY) -le 0.01
        if ($sameButton) {
            $script:FreeButtonStableCount++
        }
        else {
            $script:FreeButtonStableCount = 1
            $script:FreeButtonStableSince = Get-Date
        }
        $script:DetectedFreeButtonX = $x
        $script:DetectedFreeButtonY = $y
        $stableMilliseconds = if ($null -ne $script:FreeButtonStableSince) {
            ((Get-Date) - $script:FreeButtonStableSince).TotalMilliseconds
        }
        else { 0 }
        return $script:FreeButtonStableCount -ge 2 -and $stableMilliseconds -ge 350
    }
    $left = 0.805
    $top = 0.205
    $right = 0.975
    $bottom = 0.285
    $cyanCount = Get-ColorMatchCount $Handle $left $top $right $bottom {
        param($r, $g, $b)
        $b -gt 150 -and $g -gt 115 -and $b -gt ($r * 1.15)
    }
    return $cyanCount -ge 18
}

function Test-ResourcePlusReady {
    param([IntPtr]$Handle)
    $greenCount = Get-ColorMatchCount $Handle 0.638 0.040 0.664 0.100 {
        param($r, $g, $b)
        $g -gt 125 -and $g -gt ($r * 1.20) -and $g -gt ($b * 1.15)
    }
    return $greenCount -ge 5
}

function Test-PortraitAdWindow {
    param([IntPtr]$Handle)

    $rect = Get-WindowRectangle $Handle
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    return $height -gt ($width * 1.25)
}

function Test-AdGooglePlayBadge {
    param([IntPtr]$Handle)

    if (-not (Test-PortraitAdWindow $Handle)) {
        return $false
    }

    $greenCount = Get-ColorMatchCount $Handle 0.005 0.035 0.220 0.090 {
        param($r, $g, $b)
        $g -gt 75 -and $g -gt ($r * 1.08) -and $g -gt ($b * 0.98) -and $r -lt 180
    }
    $whiteCount = Get-ColorMatchCount $Handle 0.005 0.035 0.220 0.090 {
        param($r, $g, $b)
        $r -gt 160 -and $g -gt 160 -and $b -gt 160 -and
            ([Math]::Max($r, [Math]::Max($g, $b)) - [Math]::Min($r, [Math]::Min($g, $b))) -lt 65
    }
    return $greenCount -ge 40 -and $whiteCount -ge 3
}

function Test-StoreLoaded {
    param([IntPtr]$Handle)
    $whiteCount = Get-ColorMatchCount $Handle 0.020 0.300 0.220 0.540 {
        param($r, $g, $b)
        $r -gt 185 -and $g -gt 185 -and $b -gt 185 -and
        ([Math]::Abs($r - $g) -lt 35) -and ([Math]::Abs($g - $b) -lt 35)
    }
    return $whiteCount -ge 80
}

function Test-TopElevenReturnedAfterAd {
    param(
        [IntPtr]$Handle,
        [datetime]$Since = ([datetime]::MinValue)
    )

    # Ne vjeruj vise OpenCV slicnosti gornje trake. Player.log daje tacnu
    # Android aktivnost: reklama je AdActivity, a igra je MainPlayerNativeActivity.
    $script:ForegroundStateCheckedAt = $null
    $state = Get-BlueStacksForegroundState
    $isMainActivity = $null -ne $state -and
        $state.Package -eq 'eu.nordeus.topeleven.android' -and
        $state.Activity -eq 'eu.nordeus.common.MainPlayerNativeActivity'
    if (-not $isMainActivity) { return $false }

    # Stari MainPlayerNativeActivity zapis od prije reklame nije dokaz povratka.
    # Prihvati samo novi Android activity dogadjaj nastao nakon pokretanja reklame.
    if ($Since -ne ([datetime]::MinValue)) {
        if ($null -eq $state.EventTime -or $state.EventTime -lt $Since.AddSeconds(-1)) {
            return $false
        }
    }
    return $true
}

function Test-YellowAdControlReady {
    param([IntPtr]$Handle)

    if ($script:AdControlsAiOnly) { return $false }

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'yellow_ad_control'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    $result = $script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json
    if (-not $result.found) { return $false }

    $requiresAiConfirmation = $script:VisionEnabled -and [string]$result.kind -ne 'google_play'
    if ($requiresAiConfirmation) {
        $vision = Invoke-VisionAnalysis $Handle 'ad_control'
        $expectedAction = if ([string]$result.kind -eq 'google_play') { 'click_google_play' } else { 'click_close' }
        $candidateConfirmed = $null -ne $vision -and $vision.accepted -and
            $vision.decision.recommendedAction -eq $expectedAction -and
            [Math]::Abs(([double]$vision.decision.control.x) - ([double]$result.x)) -le 0.04 -and
            [Math]::Abs(([double]$vision.decision.control.y) - ([double]$result.y)) -le 0.04
        if (-not $candidateConfirmed) { return $false }
    }

    $script:DetectedYellowControlKind = [string]$result.kind
    # AI samo potvrdjuje vrstu kandidata; precizna OpenCV koordinata ostaje
    # izvor klika kako model ne bi pomjerio X u tekst Reward granted pilule.
    $script:DetectedYellowControlX = [double]$result.x
    $script:DetectedYellowControlY = [double]$result.y
    $confirmationSource = if ([string]$result.kind -eq 'google_play') { 'Brzi detektor je pronasao' } elseif ($requiresAiConfirmation) { 'AI je potvrdio' } else { 'OpenCV je pronasao' }
    $controlLabel = if ($script:DetectedYellowControlKind -eq 'google_play') { 'Google Play kontrolu' } else { 'zutu close kontrolu' }
    Add-Log ("{0} {1}: centar={2:N3},{3:N3}" -f $confirmationSource, $controlLabel, $script:DetectedYellowControlX, $script:DetectedYellowControlY)
    return $true
}

function Invoke-DetectedGooglePlayControl {
    param(
        [IntPtr]$Handle,
        [datetime]$AdStartedAt,
        [string]$Label = 'Google Play dugme'
    )

    if ($script:AdControlsAiOnly) { return $false }

    # Prvi klik koristi upravo detektovani centar. Neke interaktivne reklame
    # prvim klikom samo aktiviraju badge; drugi klik je dozvoljen iskljucivo
    # ako je badge ponovo vizuelno detektovan na novoj slici.
    Click-Relative $Handle $script:DetectedYellowControlX $script:DetectedYellowControlY $Label
    Wait-Agent 650
    if (Restore-AdFromGooglePlay $Handle $AdStartedAt) { return $true }

    if ((Test-YellowAdControlReady $Handle) -and
        $script:DetectedYellowControlKind -eq 'google_play') {
        Click-Relative $Handle $script:DetectedYellowControlX $script:DetectedYellowControlY "$Label - potvrda"
        Wait-Agent 1400
        if (Restore-AdFromGooglePlay $Handle $AdStartedAt) { return $true }
    }
    return $false
}

function Test-PlayDestinationScreen {
    param([IntPtr]$Handle)

    $now = Get-Date
    if ($null -ne $script:PlayDestinationCheckedAt -and
        ($now - $script:PlayDestinationCheckedAt).TotalMilliseconds -lt 250) {
        return [bool]$script:PlayDestinationCache
    }

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'play_destination'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    $result = $script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json
    $found = [bool]$result.found
    $script:PlayDestinationCheckedAt = $now
    if (-not $found) {
        $script:PlayDestinationCache = $false
        return $false
    }

    $script:DetectedPlayDestinationCloseX = [double]$result.x
    $script:DetectedPlayDestinationCloseY = [double]$result.y
    # Povratak je reverzibilna Escape radnja. Ne cekaj dvije spore AI analize:
    # BlueStacks package log je primarni signal, a ovaj strogi screen detector
    # je fallback samo za prepoznat play.google/Chrome ekran.
    $script:PlayDestinationCache = $true
    return $true
}

function Test-AdCloseReadyLegacy {
    param([IntPtr]$Handle)

    # Support both observed close-button styles:
    # 1) a white X on a dark button, 2) a dark X inside a white circle.
    $rect = Get-WindowRectangle $Handle
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $scale = [Math]::Max(0.75, [Math]::Min($width / 1647.0, $height / 955.0))
    $expectedCenters = @(
        [double[]]@(0.9515, 0.0765),
        [double[]]@(0.9660, 0.0540),
        [double[]]@(0.9835, 0.0405)
    )
    $dc = [Win32Agent]::GetDC([IntPtr]::Zero)

    try {
        $isBrightNear = {
            param([int]$X, [int]$Y)

            for ($offsetX = -1; $offsetX -le 1; $offsetX++) {
                for ($offsetY = -1; $offsetY -le 1; $offsetY++) {
                    $pixel = [Win32Agent]::GetPixel($dc, $X + $offsetX, $Y + $offsetY)
                    $r = [int]($pixel -band 0xFF)
                    $g = [int](($pixel -shr 8) -band 0xFF)
                    $b = [int](($pixel -shr 16) -band 0xFF)
                    if ($r -gt 205 -and $g -gt 205 -and $b -gt 205 -and
                        [Math]::Abs($r - $g) -lt 28 -and
                        [Math]::Abs($g - $b) -lt 28) {
                        return $true
                    }
                }
            }
            return $false
        }

        $isDarkNear = {
            param([int]$X, [int]$Y)

            for ($offsetX = -1; $offsetX -le 1; $offsetX++) {
                for ($offsetY = -1; $offsetY -le 1; $offsetY++) {
                    $pixel = [Win32Agent]::GetPixel($dc, $X + $offsetX, $Y + $offsetY)
                    $r = [int]($pixel -band 0xFF)
                    $g = [int](($pixel -shr 8) -band 0xFF)
                    $b = [int](($pixel -shr 16) -band 0xFF)
                    if ($r -lt 95 -and $g -lt 95 -and $b -lt 95 -and
                        [Math]::Abs($r - $g) -lt 45 -and
                        [Math]::Abs($g - $b) -lt 45) {
                        return $true
                    }
                }
            }
            return $false
        }

        foreach ($expectedCenter in $expectedCenters) {
            $expectedX = [int]($rect.Left + ($width * $expectedCenter[0]))
            $expectedY = [int]($rect.Top + ($height * $expectedCenter[1]))

            for ($centerShiftX = -4; $centerShiftX -le 4; $centerShiftX += 2) {
                for ($centerShiftY = -4; $centerShiftY -le 4; $centerShiftY += 2) {
                    $centerX = $expectedX + [int]($centerShiftX * $scale)
                    $centerY = $expectedY + [int]($centerShiftY * $scale)
                    $brightArms = @(0, 0, 0, 0)
                    $darkArms = @(0, 0, 0, 0)
                    $brightBackgroundPoints = 0

                    for ($distance = 3; $distance -le 10; $distance++) {
                        $step = [int]($distance * $scale)
                        $points = @(
                            [int[]]@(($centerX - $step), ($centerY - $step)),
                            [int[]]@(($centerX + $step), ($centerY - $step)),
                            [int[]]@(($centerX - $step), ($centerY + $step)),
                            [int[]]@(($centerX + $step), ($centerY + $step))
                        )

                        for ($arm = 0; $arm -lt 4; $arm++) {
                            if (& $isBrightNear $points[$arm][0] $points[$arm][1]) { $brightArms[$arm]++ }
                            if (& $isDarkNear $points[$arm][0] $points[$arm][1]) { $darkArms[$arm]++ }
                        }

                        if ($distance -ge 5) {
                            if (& $isBrightNear ($centerX - $step) $centerY) { $brightBackgroundPoints++ }
                            if (& $isBrightNear ($centerX + $step) $centerY) { $brightBackgroundPoints++ }
                            if (& $isBrightNear $centerX ($centerY - $step)) { $brightBackgroundPoints++ }
                            if (& $isBrightNear $centerX ($centerY + $step)) { $brightBackgroundPoints++ }
                        }
                    }

                    $whiteXOnDark = (& $isBrightNear $centerX $centerY) -and
                        $brightArms[0] -ge 4 -and $brightArms[1] -ge 4 -and
                        $brightArms[2] -ge 4 -and $brightArms[3] -ge 4 -and
                        $brightBackgroundPoints -le 6

                    $darkXOnWhite = (& $isDarkNear $centerX $centerY) -and
                        $darkArms[0] -ge 4 -and $darkArms[1] -ge 4 -and
                        $darkArms[2] -ge 4 -and $darkArms[3] -ge 4 -and
                        $brightBackgroundPoints -ge 16

                    if ($whiteXOnDark -or $darkXOnWhite) {
                        $script:DetectedAdCloseX = ($centerX - $rect.Left) / [double]$width
                        $script:DetectedAdCloseY = ($centerY - $rect.Top) / [double]$height
                        return $true
                    }
                }
            }
        }
        return $false
    }
    finally {
        [Win32Agent]::ReleaseDC([IntPtr]::Zero, $dc) | Out-Null
    }
}

function Start-VisionAgent {
    if (-not $script:VisionEnabled -or (Get-Date) -lt $script:VisionUnavailableUntil) { return $false }
    if ($null -ne $script:VisionAgentProcess -and -not $script:VisionAgentProcess.HasExited) { return $true }
    if (-not (Test-Path -LiteralPath $script:PythonExe) -or
        -not (Test-Path -LiteralPath $script:VisionAgentScript)) { return $false }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:PythonExe
    $startInfo.Arguments = ('"{0}" --server --config "{1}"' -f $script:VisionAgentScript, $script:VisionConfigPath)
    $startInfo.WorkingDirectory = $PSScriptRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { return $false }
    $script:VisionAgentProcess = $process
    Add-Log 'AI vision agent je pokrenut.'
    return $true
}

function Stop-VisionAgent {
    if ($null -eq $script:VisionAgentProcess) { return }
    try {
        if (-not $script:VisionAgentProcess.HasExited) {
            try {
                $script:VisionAgentProcess.StandardInput.WriteLine('{"quit":true}')
                $script:VisionAgentProcess.StandardInput.Flush()
                $script:VisionAgentProcess.WaitForExit(500) | Out-Null
            }
            catch { }
            if (-not $script:VisionAgentProcess.HasExited) { $script:VisionAgentProcess.Kill() }
        }
    }
    finally {
        $script:VisionAgentProcess.Dispose()
        $script:VisionAgentProcess = $null
    }
}

function Invoke-VisionAnalysis {
    param([IntPtr]$Handle, [string]$ExpectedState = 'ad')

    if (-not $script:VisionEnabled -or (Get-Date) -lt $script:VisionUnavailableUntil) { return $null }
    $cacheEntry = $script:VisionCacheByState[$ExpectedState]
    if ($null -ne $cacheEntry -and (Get-Date) -lt $cacheEntry.ValidUntil) {
        return $cacheEntry.Result
    }
    if (-not (Start-VisionAgent)) { return $null }

    try {
        if ($script:VisionAgentProcess.HasExited) { throw 'AI proces je zatvoren.' }
        $rect = Get-WindowRectangle $Handle
        $request = @{
            rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
            expectedState = $ExpectedState
        } | ConvertTo-Json -Compress
        $script:VisionAgentProcess.StandardInput.WriteLine($request)
        $script:VisionAgentProcess.StandardInput.Flush()
        $line = $script:VisionAgentProcess.StandardOutput.ReadLine()
        if ([string]::IsNullOrWhiteSpace($line)) { throw 'AI nije vratio rezultat.' }
        $result = $line | ConvertFrom-Json
        if (-not $result.ok) { throw [string]$result.error }
        $cacheMilliseconds = if ($result.accepted -or
            $ExpectedState -like 'ad_control_ai_only_*' -or
            $ExpectedState -like 'external_navigation_*') { $script:VisionAnalysisIntervalMs } else { 250 }
        $script:VisionCacheByState[$ExpectedState] = [PSCustomObject]@{
            Result = $result
            ValidUntil = (Get-Date).AddMilliseconds($cacheMilliseconds)
        }
        if ($result.errors.Count -gt 0) {
            Add-Log ("AI prijedlog odbijen: {0}" -f ($result.errors -join '; '))
        }
        elseif (-not $result.accepted) {
            Add-Log ("AI ceka potvrdu odluke ({0}/{1})." -f $result.stableCount, $result.requiredStableCount)
        }
        return $result
    }
    catch {
        $visionError = [string]$_.Exception.Message
        $isMalformedJson = $visionError -match 'JSONDecodeError|Unterminated string|Expecting (property name|value|delimiter)'
        if ($isMalformedJson -and -not $script:VisionMalformedJsonRetryActive) {
            Add-Log 'AI je vratio nepotpun JSON; odmah ponavljam provjeru na svjezoj slici.'
            Stop-VisionAgent
            $script:VisionCacheByState.Clear()
            $script:VisionUnavailableUntil = [datetime]::MinValue
            $script:VisionMalformedJsonRetryActive = $true
            try {
                Wait-Agent 250
                return Invoke-VisionAnalysis $Handle $ExpectedState
            }
            finally {
                $script:VisionMalformedJsonRetryActive = $false
            }
        }

        Add-Log "AI nije dostupan; sigurnosni rezim ne dozvoljava klik. $visionError"
        Stop-VisionAgent
        $script:VisionCacheByState.Clear()
        $script:VisionUnavailableUntil = (Get-Date).AddSeconds($script:VisionRetryAfterErrorSeconds)
        return $null
    }
}

function Test-AiOnlyAdControlReady {
    param(
        [IntPtr]$Handle,
        [string]$ExpectedState,
        [switch]$ForceRefresh
    )

    $script:AiTopElevenReturned = $false
    $script:AiAdVisible = $false
    # Nikad ne dozvoli da kandidat iz prethodnog framea prezivi novu provjeru.
    $script:DetectedAdCloseX = $null
    $script:DetectedAdCloseY = $null
    $script:DetectedAdCloseKind = $null
    if ($ForceRefresh) { $script:VisionCacheByState.Remove($ExpectedState) }
    $vision = Invoke-VisionAnalysis $Handle $ExpectedState
    if ($null -eq $vision -or -not $vision.accepted) { return $false }

    $action = [string]$vision.decision.recommendedAction
    if ([string]$vision.decision.screenType -eq 'ad' -and
        -not [bool]$vision.decision.topElevenReturned) {
        $script:AiAdVisible = $true
    }
    if ([string]$vision.decision.screenType -eq 'top_eleven' -and
        [bool]$vision.decision.topElevenReturned -and
        $action -eq 'none') {
        $script:AiTopElevenReturned = $true
        $script:DetectedAdCloseX = $null
        $script:DetectedAdCloseY = $null
        $script:DetectedAdCloseKind = $null
        Add-Log 'AI je potvrdio povratak Top Eleven zaglavlja s resursima.'
        return $false
    }
    if ($action -notin @('click_close', 'click_skip', 'click_google_play')) { return $false }

    $script:DetectedAdCloseX = [double]$vision.decision.control.x
    $script:DetectedAdCloseY = [double]$vision.decision.control.y
    $script:DetectedAdCloseKind = switch ($action) {
        'click_skip' { 'skip' }
        'click_google_play' { 'google_play' }
        default { 'close' }
    }

    if ($action -eq 'click_close' -and $null -ne $vision.closeRefinement -and [bool]$vision.closeRefinement.applied) {
        Add-Log ("AI je izabrao X; lokalno je centriran bez pomaka: AI={0:N3},{1:N3}, centar={2:N3},{3:N3}, razlika={4:N1}px" -f $vision.closeRefinement.aiX, $vision.closeRefinement.aiY, $vision.closeRefinement.pixelX, $vision.closeRefinement.pixelY, $vision.closeRefinement.distancePixels)
    }
    elseif ($action -eq 'click_close' -and $null -ne $vision.closeRefinement -and [bool]$vision.closeRefinement.fallbackToAiCoordinate) {
        Add-Log 'AI je svjeze potvrdio X; lokalni verifier ne poznaje ovaj stil X-a pa koristim tacan AI centar bez pomaka.'
    }

    Add-Log ("AI-only je pronasao kontrolu: akcija={0}, confidence={1:N2}, centar={2:N3},{3:N3}" -f $action, $vision.decision.control.confidence, $script:DetectedAdCloseX, $script:DetectedAdCloseY)
    return $true
}

function Confirm-AiAdCloseImmediatelyBeforeClick {
    param([IntPtr]$Handle, [string]$Label = 'reklama')

    $freshState = "ad_control_ai_only_preclick_$((Get-Date).Ticks)"
    $ready = Test-AiOnlyAdControlReady $Handle $freshState -ForceRefresh
    if ($script:AiTopElevenReturned) {
        Add-Log "$Label se vec sama zatvorila; ponistavam stari X i ne klikcem."
        return 'returned'
    }
    if ($ready -and $script:DetectedAdCloseKind -eq 'close') {
        return 'close'
    }
    Add-Log "$Label vise nema svjeze potvrdjen X; stara koordinata se nece kliknuti."
    return 'not_confirmed'
}

function Try-RecoverConnectionInterruptedPopup {
    param([IntPtr]$Handle)

    if ($script:ConnectionPopupRecoveryActive) { return $false }
    if (((Get-Date) - $script:ConnectionPopupLastCheckAt).TotalSeconds -lt 2.0) { return $false }
    $script:ConnectionPopupLastCheckAt = Get-Date
    $script:ConnectionPopupRecoveryActive = $true
    $formWasTopMost = $form.TopMost
    $form.TopMost = $false
    try {
        [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
        Wait-Agent 120
        $expectedState = "connection_interrupted_popup_$((Get-Date).Ticks)"
        $vision = Invoke-VisionAnalysis $Handle $expectedState
        $connectionFound = $null -ne $vision -and [bool]$vision.accepted -and
            [string]$vision.decision.screenType -eq 'top_eleven' -and
            [string]$vision.decision.recommendedAction -eq 'click_connection_confirm' -and
            [string]$vision.decision.control.type -eq 'connection_confirm' -and
            $null -ne $vision.decision.control.x -and $null -ne $vision.decision.control.y
        if ($connectionFound) {
            Add-Log ("AI je prepoznao popup VEZA JE PREKINUTA; klikcem potvrdu na {0:N3},{1:N3}." -f
                [double]$vision.decision.control.x, [double]$vision.decision.control.y)
            Click-Relative $Handle ([double]$vision.decision.control.x) ([double]$vision.decision.control.y) 'VEZA JE PREKINUTA - potvrda AI'
            Set-Status ("Veza je bila prekinuta - cekam {0:N1}s ponovno ucitavanje i nastavljam isti tok..." -f
                ($script:ConnectionRecoveryWaitMs / 1000.0)) ([System.Drawing.Color]::FromArgb(255, 210, 100))
            $script:VisionCacheByState.Clear()
            Wait-Agent $script:ConnectionRecoveryWaitMs
            Add-Log 'Cekanje nakon potvrde veze je zavrseno; nastavljam od istog workflow koraka.'
            return $true
        }

        $popupState = "incidental_top_eleven_popup_$((Get-Date).Ticks)"
        $popupVision = Invoke-VisionAnalysis $Handle $popupState
        $popupFound = $null -ne $popupVision -and [bool]$popupVision.accepted -and
            [string]$popupVision.decision.screenType -eq 'top_eleven' -and
            [string]$popupVision.decision.recommendedAction -eq 'click_incidental_popup_close' -and
            [string]$popupVision.decision.control.type -eq 'incidental_popup_close' -and
            $null -ne $popupVision.decision.control.x -and $null -ne $popupVision.decision.control.y
        if (-not $popupFound) { return $false }

        Add-Log ("AI je prepoznao neocekivani Top Eleven popup; zatvaram ga na {0:N3},{1:N3}." -f
            [double]$popupVision.decision.control.x, [double]$popupVision.decision.control.y)
        Click-Relative $Handle ([double]$popupVision.decision.control.x) ([double]$popupVision.decision.control.y) 'Neocekivani Top Eleven popup - AI X'
        Set-Status 'Neocekivani popup je zatvoren - cekam stabilizaciju i nastavljam isti tok...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
        $script:VisionCacheByState.Clear()
        Wait-Agent $script:LongTransitionBufferMs
        return $true
    }
    finally {
        $form.TopMost = $formWasTopMost
        $script:ConnectionPopupRecoveryActive = $false
    }
}

function Test-AiExternalNavigationVisible {
    param(
        [IntPtr]$Handle,
        [datetime]$AdStartedAt,
        [switch]$ForceRefresh
    )

    $expectedState = "external_navigation_$($AdStartedAt.Ticks)"
    if ($ForceRefresh) { $script:VisionCacheByState.Remove($expectedState) }
    $vision = Invoke-VisionAnalysis $Handle $expectedState
    if ($null -eq $vision -or -not $vision.accepted) { return $null }
    $visible = $null -ne $vision -and $vision.accepted -and
        [string]$vision.decision.screenType -in @('google_play_store', 'play_google_chrome') -and
        [string]$vision.decision.recommendedAction -eq 'send_back'
    if ($visible) { Add-Log 'AI je potvrdio da je Google Play/Chrome jos uvijek otvoren.' }
    return $visible
}

function Get-AiMourinhoWarning {
    param([IntPtr]$Handle)

    $vision = Invoke-VisionAnalysis $Handle 'mourinho_warning'
    if ($null -eq $vision -or -not $vision.accepted) { return $null }
    if ([string]$vision.decision.screenType -ne 'top_eleven' -or
        [string]$vision.decision.recommendedAction -ne 'click_target' -or
        [string]$vision.decision.control.type -ne 'mourinho_warning') {
        return $null
    }

    $target = [PSCustomObject]@{
        x = [double]$vision.decision.control.x
        y = [double]$vision.decision.control.y
        confidence = [double]$vision.decision.control.confidence
    }
    Add-Log ("AI je locirao Mourinho dugme: confidence={0:N2}, centar={1:N3},{2:N3}" -f $target.confidence, $target.x, $target.y)
    return $target
}

function Start-XDetector {
    if ($null -ne $script:XDetectorProcess -and -not $script:XDetectorProcess.HasExited) {
        return
    }
    if (-not (Test-Path -LiteralPath $script:PythonExe)) {
        throw "Python runtime za OpenCV nije pronadjen: $script:PythonExe"
    }
    if (-not (Test-Path -LiteralPath $script:XDetectorScript)) {
        throw "OpenCV detektor nije pronadjen: $script:XDetectorScript"
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:PythonExe
    $startInfo.Arguments = ('"{0}" --server' -f $script:XDetectorScript)
    $startInfo.WorkingDirectory = $PSScriptRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'Nije moguce pokrenuti OpenCV X detektor.'
    }

    $script:XDetectorProcess = $process
    $script:XDetectorStableCount = 0
    $script:XDetectorStableSince = $null
    $script:XDetectorLastX = $null
    $script:XDetectorLastY = $null
    $script:XDetectorLastPolarity = $null
    $script:XDetectorLastSide = $null
    $script:XDetectorLastKind = $null
    Add-Log 'OpenCV pomocni recognizer ekrana je pokrenut; reklamna dugmad ostaju AI-only.'
}

function Stop-XDetector {
    if ($null -eq $script:XDetectorProcess) { return }
    try {
        if (-not $script:XDetectorProcess.HasExited) {
            try {
                $script:XDetectorProcess.StandardInput.WriteLine('{"quit":true}')
                $script:XDetectorProcess.StandardInput.Flush()
                $script:XDetectorProcess.WaitForExit(500) | Out-Null
            }
            catch { }
            if (-not $script:XDetectorProcess.HasExited) {
                $script:XDetectorProcess.Kill()
            }
        }
    }
    finally {
        $script:XDetectorProcess.Dispose()
        $script:XDetectorProcess = $null
    }
}

function Test-AdCloseReady {
    param([IntPtr]$Handle)

    if ($script:AdControlsAiOnly) { return $false }

    Start-XDetector
    if ($script:XDetectorProcess.HasExited) {
        $details = $script:XDetectorProcess.StandardError.ReadToEnd()
        throw "OpenCV X detektor se neocekivano zatvorio. $details"
    }

    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    $line = $script:XDetectorProcess.StandardOutput.ReadLine()
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw 'OpenCV X detektor nije vratio rezultat.'
    }

    $result = $line | ConvertFrom-Json
    if (-not $result.found) {
        $script:XDetectorStableCount = 0
        $script:XDetectorStableSince = $null
        $script:XDetectorLastX = $null
        $script:XDetectorLastY = $null
        $script:XDetectorLastPolarity = $null
        $script:XDetectorLastSide = $null
        $script:XDetectorLastKind = $null
        return $false
    }

    $x = [double]$result.x
    $y = [double]$result.y
    $polarity = [string]$result.polarity
    $side = if ($null -ne $result.side) { [string]$result.side } else { 'right' }
    $kind = if ($null -ne $result.kind) { [string]$result.kind } else { 'close' }
    $sameTarget = $null -ne $script:XDetectorLastX -and
        [Math]::Abs($x - $script:XDetectorLastX) -le 0.006 -and
        [Math]::Abs($y - $script:XDetectorLastY) -le 0.006 -and
        $polarity -eq $script:XDetectorLastPolarity -and
        $side -eq $script:XDetectorLastSide -and
        $kind -eq $script:XDetectorLastKind

    if ($sameTarget) {
        $script:XDetectorStableCount++
    }
    else {
        $script:XDetectorStableCount = 1
        $script:XDetectorStableSince = Get-Date
    }
    $script:XDetectorLastX = $x
    $script:XDetectorLastY = $y
    $script:XDetectorLastPolarity = $polarity
    $script:XDetectorLastSide = $side
    $script:XDetectorLastKind = $kind

    $stableMilliseconds = if ($null -ne $script:XDetectorStableSince) {
        ((Get-Date) - $script:XDetectorStableSince).TotalMilliseconds
    }
    else { 0 }
    $highConfidenceX = ([double]$result.score -ge 235 -and [double]$result.shape -ge 98)
    $portraitHighConfidenceX = $highConfidenceX -and (Test-PortraitAdWindow $Handle)
    $requiredStableCount = if ($portraitHighConfidenceX) { 2 } elseif ($highConfidenceX) { 3 } else { 5 }
    $requiredStableMilliseconds = if ($portraitHighConfidenceX) { 250 } elseif ($highConfidenceX) { 450 } else { 800 }
    if ($script:XDetectorStableCount -lt $requiredStableCount -or
        $stableMilliseconds -lt $requiredStableMilliseconds) { return $false }

    # OpenCV je samo brzi senzor kandidata. Dok je AI ukljucen, klik je
    # dozvoljen iskljucivo nakon dvije AI potvrde istog tipa i koordinata.
    if ($script:VisionEnabled) {
        $vision = Invoke-VisionAnalysis $Handle 'ad_control'
        $expectedAction = if ($kind -eq 'skip') { 'click_skip' } else { 'click_close' }
        $candidateConfirmed = $null -ne $vision -and $vision.accepted -and
            $vision.decision.recommendedAction -eq $expectedAction -and
            [Math]::Abs(([double]$vision.decision.control.x) - $x) -le 0.04 -and
            [Math]::Abs(([double]$vision.decision.control.y) - $y) -le 0.04
        if (-not $candidateConfirmed) { return $false }

        # AI potvrdjuje da kandidat jeste odgovarajuca kontrola, ali klik koristi
        # precizni OpenCV centar. Ovo sprjecava klik unutar Reward granted teksta.
        $script:DetectedAdCloseX = $x
        $script:DetectedAdCloseY = $y
        $script:DetectedAdCloseKind = $kind
        Add-Log ("AI je potvrdio OpenCV kandidata: vrsta={0}, confidence={1:N2}, centar={2:N3},{3:N3}" -f $kind, $vision.decision.control.confidence, $script:DetectedAdCloseX, $script:DetectedAdCloseY)
        return $true
    }

    $script:DetectedAdCloseX = $x
    $script:DetectedAdCloseY = $y
    $script:DetectedAdCloseKind = $kind
    Add-Log ("OpenCV kontrola: vrsta={0}, confidence={1}, oblik={2}, tip={3}, centar={4:N3},{5:N3}" -f $kind, $result.score, $result.shape, $polarity, $x, $y)
    return $true
}

function Wait-ForAdExitOrControl {
    param(
        [IntPtr]$Handle,
        [int]$TimeoutSeconds = 10,
        [datetime]$AdStartedAt = ([datetime]::MinValue)
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $returnedStableCount = 0
    $nextAiProbeAt = (Get-Date).AddMilliseconds(800)
    $expectedState = "ad_control_ai_only_followup_$((Get-Date).Ticks)"
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        if (Test-TopElevenReturnedAfterAd $Handle $AdStartedAt) {
            $returnedStableCount++
            if ($returnedStableCount -eq 1) {
                Add-Log 'Top Eleven MainPlayerNativeActivity je pronadjena; potvrdjujem povratak...'
            }
            if ($returnedStableCount -ge 2) {
                Add-Log 'Povratak u Top Eleven potvrden je Android aktivnoscu, bez OpenCV trake.'
                return 'exited'
            }
            Start-Sleep -Milliseconds 150
            continue
        }
        else {
            $returnedStableCount = 0
        }

        $playRestoreTriggered = $false
        if ($AdStartedAt -ne ([datetime]::MinValue)) {
            $playRestoreTriggered = Restore-AdFromGooglePlay $Handle $AdStartedAt
        }
        if ($playRestoreTriggered) {
            Start-Sleep -Milliseconds 100
            continue
        }
        if ((Get-Date) -ge $nextAiProbeAt) {
            $nextAiProbeAt = (Get-Date).AddSeconds($script:VisionAiProbeIntervalSeconds)
            $aiControlReady = Test-AiOnlyAdControlReady $Handle $expectedState
            if ($script:AiTopElevenReturned) {
                Add-Log 'Povratak u Top Eleven potvrden je AI analizom trenutne slike.'
                return 'exited'
            }
            if ($aiControlReady) {
                if ($script:DetectedAdCloseKind -eq 'skip') {
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY '>> - AI follow-up'
                    Wait-Agent $script:TransitionBufferMs
                    $expectedState = "ad_control_ai_only_followup_$((Get-Date).Ticks)"
                    $nextAiProbeAt = Get-Date
                    continue
                }
                if ($script:DetectedAdCloseKind -eq 'google_play') {
                    $script:LastGooglePlayClickAt = Get-Date
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY 'Google Play - AI follow-up'
                    Wait-Agent 1500
                    Restore-AdFromGooglePlay $Handle $AdStartedAt | Out-Null
                    $expectedState = "ad_control_ai_only_followup_$((Get-Date).Ticks)"
                    $nextAiProbeAt = Get-Date
                    continue
                }
                return 'control'
            }
        }
        Start-Sleep -Milliseconds 120
    }
    return 'unknown'
}

function Dismiss-GamePopups {
    param([IntPtr]$Handle)

    Set-Status 'Provjeravam i zatvaram popupove...'
    Wait-Agent $script:ShortTransitionBufferMs

    $clearChecks = 0
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        if (Test-ResourcePlusReady $Handle) {
            $clearChecks++
            if ($clearChecks -ge 1) {
                Add-Log 'Glavni ekran je cist; zeleni + je ponovo aktivan.'
                return
            }
            Wait-Agent 50
            continue
        }

        $clearChecks = 0
        switch ($attempt % 4) {
            1 { Send-Escape $Handle }
            2 { Click-Relative $Handle 0.940 0.165 'moguci X na popupu' }
            3 { Click-Relative $Handle 0.500 0.840 'moguce dugme ZATVORI' }
            0 { Click-Relative $Handle 0.900 0.145 'alternativni X na popupu' }
        }
        Wait-Agent $script:ShortTransitionBufferMs
    }

    Add-Log 'Nije potvrdjen cist ekran; pokusat cu otvoriti prodavnicu i provjeriti rezultat.'
}

function Open-Store {
    param([IntPtr]$Handle)

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Set-Status "Otvaram prodavnicu preko zelenog + dugmeta (pokusaj $attempt/3)..."
        Click-Relative $Handle 0.651 0.071 'zeleni + za odmore'

        $deadline = (Get-Date).AddMilliseconds($script:LongTransitionBufferMs)
        while ((Get-Date) -lt $deadline) {
            Test-Cancelled
            if (Test-StoreLoaded $Handle) {
                Add-Log 'Prodavnica je otvorena.'
                return
            }
            Start-Sleep -Milliseconds 50
        }

        Add-Log 'Prodavnica se nije otvorila; vjerovatno je ostao popup.'
        switch ($attempt) {
            1 { Send-Escape $Handle }
            2 { Click-Relative $Handle 0.940 0.165 'moguci X na popupu' }
            3 { Click-Relative $Handle 0.500 0.840 'moguce dugme ZATVORI' }
            4 { Send-Escape $Handle }
        }
        Wait-Agent $script:ShortTransitionBufferMs
    }

    throw 'Nije uspjelo otvoriti prodavnicu nakon zatvaranja popupova.'
}

function Open-TeamRest {
    param([IntPtr]$Handle)

    Set-Status 'Otvaram bocni meni...'
    $form.TopMost = $false
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent $script:ShortTransitionBufferMs

    Click-GameRelative $Handle 0.014 0.068 'bocni meni'
    Wait-Agent $script:TransitionBufferMs
    Click-GameRelative $Handle 0.087 0.189 'Trening'
    Wait-Agent $script:LongTransitionBufferMs
    Click-GameRelative $Handle 0.124 0.914 'Fizio centar'
    Wait-Agent $script:TransitionBufferMs

    $form.TopMost = $true
    Add-Log 'Otvoren je Fizio centar; pocetna pozicija ce biti izabrana iz liste.'
}

function Scroll-PlayerList {
    param(
        [IntPtr]$Handle,
        [ValidateSet('Up', 'Down')]
        [string]$Direction
    )

    $rect = Get-GameViewportRectangle $Handle
    $x = [int]($rect.Left + (($rect.Right - $rect.Left) * 0.80))
    $y = [int]($rect.Top + (($rect.Bottom - $rect.Top) * 0.55))
    if ($script:DryRun) {
        Add-Log "DRY RUN lista igraca: scroll $Direction na ($x, $y)"
        return
    }
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    [Win32Agent]::SetCursorPos($x, $y) | Out-Null
    Wait-Agent 50

    for ($step = 1; $step -le $script:ScrollSteps; $step++) {
        if ($Direction -eq 'Down') {
            $wheelDown = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int]-120), 0)
            [Win32Agent]::mouse_event(0x0800, 0, 0, $wheelDown, [UIntPtr]::Zero)
        }
        else {
            [Win32Agent]::mouse_event(0x0800, 0, 0, 120, [UIntPtr]::Zero)
        }
        Wait-Agent 50
    }
    Wait-Agent 900
    Add-Log "Lista igraca: scroll $Direction"
}

function Wait-TeamRestAdLaunchEvidence {
    param(
        [IntPtr]$Handle,
        [datetime]$ClickedAt,
        [string]$PlayerLabel
    )

    $deadline = (Get-Date).AddSeconds(12)
    $buttonCheckStartsAt = (Get-Date).AddMilliseconds(700)
    $nextButtonCheckAt = $buttonCheckStartsAt
    $nextAiProbeAt = (Get-Date).AddSeconds(2)
    $retryAllowedAt = $ClickedAt.AddSeconds(8)
    $launchState = "ad_control_ai_only_launch_$($ClickedAt.Ticks)"
    $readyStableCount = 0
    $readyStableSince = $null
    $lastReadyX = $null
    $lastReadyY = $null
    $lastButtonSnapshot = $null
    $script:DetectedFreeButtonX = $null
    $script:DetectedFreeButtonY = $null
    $script:FreeButtonStableCount = 0
    $script:FreeButtonStableSince = $null
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $foreground = Get-BlueStacksForegroundState
        if ($null -ne $foreground -and $foreground.EventTime -ge $ClickedAt.AddMilliseconds(-500)) {
            $isAdActivity = $foreground.Package -eq 'eu.nordeus.topeleven.android' -and
                $foreground.Activity -like '*AdActivity*'
            $isExternalDestination = $foreground.Package -in @(
                'com.android.vending',
                'com.google.android.gms',
                'com.android.chrome'
            )
            if ($isAdActivity -or $isExternalDestination) {
                Add-Log "Pokretanje reklame za $PlayerLabel potvrdeno je Android aktivnoscu."
                return [PSCustomObject]@{ Proceed = $true; Observed = $true }
            }
        }

        if ((Get-Date) -ge $nextButtonCheckAt) {
            $nextButtonCheckAt = (Get-Date).AddMilliseconds(250)
            $lastButtonSnapshot = Get-TeamRestFreeButtonSnapshot $Handle
            if ([bool]$lastButtonSnapshot.ready) {
                $readyX = [double]$lastButtonSnapshot.x
                $readyY = [double]$lastButtonSnapshot.y
                $sameReadyButton = $null -ne $lastReadyX -and
                    [Math]::Abs($readyX - $lastReadyX) -le 0.01 -and
                    [Math]::Abs($readyY - $lastReadyY) -le 0.01
                if ($sameReadyButton) {
                    $readyStableCount++
                }
                else {
                    $readyStableCount = 1
                    $readyStableSince = Get-Date
                }
                $lastReadyX = $readyX
                $lastReadyY = $readyY
            }
            else {
                $readyStableCount = 0
                $readyStableSince = $null
                $lastReadyX = $null
                $lastReadyY = $null
            }
            $readyStableMilliseconds = if ($null -ne $readyStableSince) {
                ((Get-Date) - $readyStableSince).TotalMilliseconds
            }
            else { 0 }
            if ((Get-Date) -ge $retryAllowedAt -and
                $readyStableCount -ge 2 -and
                $readyStableMilliseconds -ge 500) {
                Add-Log "Tekst BESPLATNO za $PlayerLabel je jos uvijek vidljiv nakon klika; reklama nije pokrenuta."
                return [PSCustomObject]@{ Proceed = $false; Observed = $false }
            }
        }

        if ($script:VisionEnabled -and (Get-Date) -ge $nextAiProbeAt) {
            $nextAiProbeAt = (Get-Date).AddSeconds(4)
            Test-AiOnlyAdControlReady $Handle $launchState -ForceRefresh | Out-Null
            if ($script:AiAdVisible) {
                Add-Log "Pokretanje reklame za $PlayerLabel potvrdeno je AI analizom."
                return [PSCustomObject]@{ Proceed = $true; Observed = $true }
            }
        }
        Wait-Agent 100
    }

    if ($null -ne $lastButtonSnapshot -and [bool]$lastButtonSnapshot.buttonVisible) {
        $buttonState = if ([bool]$lastButtonSnapshot.ready) { 'BESPLATNO' } else { 'tri tacke/loading' }
        Add-Log "Dugme za $PlayerLabel je i dalje u stanju '$buttonState' bez reklame; vracam se na sigurno cekanje."
        return [PSCustomObject]@{ Proceed = $false; Observed = $false }
    }
    Add-Log "BESPLATNO za $PlayerLabel je nestalo, ali reklama jos nije potvrdena; nastavljam sigurno cekanje bez dodatnog klika."
    return [PSCustomObject]@{ Proceed = $true; Observed = $false }
}

function Wait-ManualTeamRestAd {
    param(
        [IntPtr]$Handle,
        [string]$PlayerLabel
    )

    $adStartedAt = $null
    $launchObserved = $false
    for ($launchAttempt = 1; $launchAttempt -le 3; $launchAttempt++) {
        $script:DetectedFreeButtonX = $null
        $script:DetectedFreeButtonY = $null
        $script:FreeButtonStableCount = 0
        $script:FreeButtonStableSince = $null
        Set-Status "Cekam stvarni tekst BESPLATNO za $PlayerLabel; tri tacke nisu dovoljne..."
        Wait-ForCondition "BESPLATNO za $PlayerLabel" 30 {
            Test-FreeButtonReady $Handle
        } | Out-Null

        [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
        Wait-Agent 120
        if (-not (Test-FreeButtonReady $Handle)) {
            Add-Log "BESPLATNO za $PlayerLabel se promijenilo prije klika; cekam novu potvrdu teksta."
            Wait-ForCondition "ponovna potvrda BESPLATNO za $PlayerLabel" 15 {
                Test-FreeButtonReady $Handle
            } | Out-Null
        }
        if ($null -eq $script:DetectedFreeButtonX -or $null -eq $script:DetectedFreeButtonY) {
            throw "BESPLATNO za $PlayerLabel nema potvrdenu dinamicku koordinatu."
        }
        Set-Status "Tekst BESPLATNO je potvrden za $PlayerLabel - klik $launchAttempt/3." ([System.Drawing.Color]::FromArgb(120, 240, 150))
        $clickedAt = Get-Date
        Click-Relative $Handle $script:DetectedFreeButtonX $script:DetectedFreeButtonY "BESPLATNO - $PlayerLabel"
        $launchResult = Wait-TeamRestAdLaunchEvidence $Handle $clickedAt $PlayerLabel
        if ([bool]$launchResult.Proceed) {
            $adStartedAt = $clickedAt
            $launchObserved = [bool]$launchResult.Observed
            break
        }
        Set-Status "Reklama za $PlayerLabel nije pokrenuta - vracam se na cekanje pravog BESPLATNO." ([System.Drawing.Color]::FromArgb(255, 210, 100))
        Wait-Agent 300
    }
    if ($null -eq $adStartedAt) {
        throw "Reklama za $PlayerLabel nije pokrenuta nakon tri potvrdena BESPLATNO klika."
    }

    $launchStatus = if ($launchObserved) { 'potvrdeno je pokrenuta' } else { 'se ucitava' }
    Set-Status "Reklama za $PlayerLabel $launchStatus. AI nadzor dugmadi je aktivan..."
    $adCloseDeadline = (Get-Date).AddMinutes(5)
    $xDetectionStartsAt = (Get-Date).AddSeconds($script:XDetectionDelaySeconds)
    $aiOnlyFallbackStartsAt = $adStartedAt.AddSeconds($script:VisionAiOnlyFallbackAfterSeconds)
    # Nema posebnog AI probea nakon 5 sekundi; prvi je puni redovni interval.
    $nextAiProbeAt = $adStartedAt.AddSeconds($script:VisionAiProbeIntervalSeconds)
    $aiOnlyExpectedState = "ad_control_ai_only_$($adStartedAt.Ticks)"
    $aiOnlyFallbackLogged = $false
    $googlePlayBadgeClicked = $false
    $detectedGooglePlayAttemptCount = 0
    $nextDetectedGooglePlayAttemptAt = $adStartedAt
    $googlePlayReminderAt = (Get-Date).AddSeconds($script:AdWaitSeconds + 15)
    $googlePlayReminderShown = $false
    $xDetectionStarted = $false
    $adCloseReady = $false
    $nextAdWakeTapAt = $adStartedAt.AddSeconds($script:AdWakeTapAfterSeconds)
    $adWakeBurstUntil = $null
    $adWakeTapCount = 0
    $adObserved = $launchObserved

    while ((Get-Date) -lt $adCloseDeadline) {
        Test-Cancelled
        if (Restore-AdFromGooglePlay $Handle $adStartedAt) {
            $googlePlayBadgeClicked = $true
            $adObserved = $true
            Start-Sleep -Milliseconds 50
            continue
        }
        if ((Get-Date) -ge $nextAdWakeTapAt -and $adWakeTapCount -lt $script:AdWakeTapMaximum) {
            $adWakeTapCount++
            Set-Status "Reklama za $PlayerLabel dugo traje - dodirujem ekran da ponovo prikazem kratku kontrolu..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            Click-Relative $Handle 0.500 0.620 "reklama za $PlayerLabel - probudi skrivenu kontrolu"
            $adWakeBurstUntil = (Get-Date).AddSeconds($script:AdWakeBurstSeconds)
            $nextAdWakeTapAt = (Get-Date).AddSeconds($script:AdWakeTapIntervalSeconds)
            $script:VisionCacheByState.Remove($aiOnlyExpectedState)
            $nextAiProbeAt = Get-Date
            Add-Log "Wake provjera za $PlayerLabel`: AI provjera krece odmah."
        }
        $wakeBurstActive = $null -ne $adWakeBurstUntil -and (Get-Date) -lt $adWakeBurstUntil
        $aiOnlyFallbackActive = $false
        if ($aiOnlyFallbackActive) {
            if (-not $aiOnlyFallbackLogged) {
                $aiOnlyFallbackLogged = $true
                Set-Status "Reklama je i dalje otvorena nakon $script:VisionAiOnlyFallbackAfterSeconds sekundi - prelazim na AI-only detekciju za $PlayerLabel..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            }
        }
        if ($script:VisionEnabled -and (Get-Date) -ge $nextAiProbeAt) {
            $nextAiProbeAt = (Get-Date).AddSeconds($script:VisionAiProbeIntervalSeconds)
            Add-Log "AI periodicna provjera kontrole za $PlayerLabel..."
            $aiControlReady = Test-AiOnlyAdControlReady $Handle $aiOnlyExpectedState
            if ($script:AiAdVisible) { $adObserved = $true }
            if ($script:AiTopElevenReturned -and $adObserved) {
                Add-Log "AI je potvrdio da je reklama za $PlayerLabel vec zatvorena."
                Wait-Agent $script:TransitionBufferMs
                return
            }
            if ($script:AiTopElevenReturned -and -not $adObserved) {
                Add-Log 'AI jos vidi pocetni Top Eleven ekran, ali reklama nije bila opazena; ne proglasavam zavrsetak.'
            }
            if ($aiControlReady) {
                if ($script:DetectedAdCloseKind -eq 'skip') {
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY ">> - AI-only nastavi reklamu za $PlayerLabel"
                    Wait-Agent $script:TransitionBufferMs
                    $aiOnlyExpectedState = "ad_control_ai_only_$((Get-Date).Ticks)"
                    continue
                }
                if ($script:DetectedAdCloseKind -eq 'google_play') {
                    $script:LastGooglePlayClickAt = Get-Date
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY 'Google Play dugme - AI-only'
                    Wait-Agent 2000
                    Restore-AdFromGooglePlay $Handle $adStartedAt | Out-Null
                    $aiOnlyExpectedState = "ad_control_ai_only_$((Get-Date).Ticks)"
                    continue
                }
                $adCloseReady = $true
                break
            }
        }
        if ($aiOnlyFallbackActive) {
            Start-Sleep -Milliseconds 50
            continue
        }
        if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt -and (Test-YellowAdControlReady $Handle)) {
            if ($script:DetectedYellowControlKind -eq 'google_play') {
                # A real close X always wins over a yellow Play candidate.
                if (Test-AdCloseReady $Handle) {
                    if ($script:DetectedAdCloseKind -eq 'skip') {
                        Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY ">> - nastavi reklamu za $PlayerLabel"
                        Wait-Agent $script:TransitionBufferMs
                        $script:XDetectorStableCount = 0
                        $script:XDetectorStableSince = $null
                        continue
                    }
                    $adCloseReady = $true
                    break
                }
                if (-not $googlePlayBadgeClicked -and
                    $detectedGooglePlayAttemptCount -lt 3 -and
                    (Get-Date) -ge $nextDetectedGooglePlayAttemptAt) {
                    $detectedGooglePlayAttemptCount++
                    $nextDetectedGooglePlayAttemptAt = (Get-Date).AddSeconds(4)
                    Set-Status "Google Play dugme za $PlayerLabel je pronadjeno - otvaram Store..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    if (Invoke-DetectedGooglePlayControl $Handle $adStartedAt 'Google Play dugme') {
                        $googlePlayBadgeClicked = $true
                    }
                    continue
                }
            }
            else {
                $script:DetectedAdCloseX = $script:DetectedYellowControlX
                $script:DetectedAdCloseY = $script:DetectedYellowControlY
                $script:DetectedAdCloseKind = 'close'
                $adCloseReady = $true
                Set-Status "Zuti X za $PlayerLabel je pronadjen." ([System.Drawing.Color]::FromArgb(120, 240, 150))
                break
            }
        }
        if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt) {
            if (-not $xDetectionStarted) {
                $xDetectionStarted = $true
                Set-Status "Pokrecem brzu detekciju X-a za $PlayerLabel..."
            }
            if (Test-AdCloseReady $Handle) {
                if ($script:DetectedAdCloseKind -eq 'skip') {
                    Set-Status "Dugme >> za $PlayerLabel je spremno - nastavljam reklamu..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY ">> - nastavi reklamu za $PlayerLabel"
                    Wait-Agent $script:TransitionBufferMs
                    $script:XDetectorStableCount = 0
                    $script:XDetectorStableSince = $null
                    continue
                }
                $adCloseReady = $true
                break
            }
        }

        if (-not $googlePlayReminderShown -and (Get-Date) -ge $googlePlayReminderAt) {
            $googlePlayReminderShown = $true
            Set-Status 'X jos nije dostupan; nastavljam cekati i automatski nadgledati Google Play Store.' ([System.Drawing.Color]::FromArgb(255, 210, 100))
        }

        Start-Sleep -Milliseconds 50
    }

    if (-not $adCloseReady) {
        throw "X za $PlayerLabel nije prepoznat u roku od 5 minuta."
    }

    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Set-Status "X je dostupan za $PlayerLabel - zatvaram reklamu automatski." ([System.Drawing.Color]::FromArgb(120, 240, 150))

    $adClosed = $false
    while ((Get-Date) -lt $adCloseDeadline -and -not $adClosed) {
        Test-Cancelled
        $preClickState = Confirm-AiAdCloseImmediatelyBeforeClick $Handle "Reklama za $PlayerLabel"
        if ($preClickState -eq 'returned') {
            $adClosed = $true
            break
        }
        if ($preClickState -ne 'close') {
            Set-Status "Reklama za $PlayerLabel je jos pod nadzorom - cekam novu svjezu AI potvrdu X-a ili povratka..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            Wait-Agent 1000
            continue
        }
        if ($null -eq $script:DetectedAdCloseX -or $null -eq $script:DetectedAdCloseY) {
            throw "AI nije vratio koordinate X-a za $PlayerLabel."
        }
        $closeX = [double]$script:DetectedAdCloseX
        $closeY = [double]$script:DetectedAdCloseY
        Click-Relative $Handle $closeX $closeY "X - zatvori reklamu za $PlayerLabel"
        Wait-Agent $script:TransitionBufferMs
        if (Restore-AdFromGooglePlay $Handle $adStartedAt) {
            $xAfterStore = Wait-ForAdXAfterGooglePlayReturn $Handle $adCloseDeadline $adStartedAt $PlayerLabel
            if ($script:AiTopElevenReturned) {
                $adClosed = $true
                break
            }
            if (-not $xAfterStore) {
                throw "Nakon povratka iz Google Play Storea X za $PlayerLabel nije pronadjen."
            }
            continue
        }
        # Povratak je siguran read-only AI/Android korak. Daj mu dovoljno vremena
        # za jos jednu provjeru ako Gemini jednom vrati prekinut JSON.
        $exitState = Wait-ForAdExitOrControl $Handle 35 $adStartedAt
        if ($exitState -eq 'exited') {
            $adClosed = $true
            Add-Log "Top Eleven je potvrden Android aktivnoscu ili AI analizom nakon reklame za $PlayerLabel."
            break
        }
        if ($exitState -eq 'control') {
            Add-Log "Reklama za $PlayerLabel je jos otvorena; pronadjena je nova aktivna kontrola."
            continue
        }
        Add-Log "Povratak za $PlayerLabel jos nije potvrden; nastavljam automatski nadzor umjesto prekida."
        Wait-Agent 1000
    }

    if (-not $adClosed) {
        throw "X je kliknut, ali reklama za $PlayerLabel nije zatvorena."
    }

    Wait-Agent $script:TransitionBufferMs
    Add-Log "Zavrsen automatski odmor: $PlayerLabel"
}

function Run-TeamRestManualQueue {
    param(
        [IntPtr]$Handle,
        [string]$StartKey = 'GK'
    )

    $startIndex = -1
    for ($index = 0; $index -lt $script:TeamRestQueue.Count; $index++) {
        if ([string]$script:TeamRestQueue[$index].Key -eq $StartKey) {
            $startIndex = $index
            break
        }
    }
    if ($startIndex -lt 0) {
        throw "Nepoznata pocetna pozicija za odmor igraca: $StartKey"
    }

    $startItem = $script:TeamRestQueue[$startIndex]
    Add-Log ("Odmor igraca pocinje od: {0} (stavka {1}/{2})." -f $startItem.Display, ($startIndex + 1), $script:TeamRestQueue.Count)
    Set-Status ("Odmor igraca pocinje od {0}." -f $startItem.Display) ([System.Drawing.Color]::FromArgb(120, 240, 150))

    # Fizio centar se uvijek otvara na gornjoj grupi. Prije prvog i svakog
    # sljedeceg igraca lista se dovodi u prikaz koji pripada toj poziciji.
    $currentView = 'Top'
    for ($index = $startIndex; $index -lt $script:TeamRestQueue.Count; $index++) {
        Test-Cancelled
        $player = $script:TeamRestQueue[$index]
        if ([string]$player.View -ne $currentView) {
            $scrollDirection = if ([string]$player.View -eq 'Bottom') { 'Down' } else { 'Up' }
            Scroll-PlayerList $Handle $scrollDirection
            $currentView = [string]$player.View
        }
        Click-GameRelative $Handle 0.976 $player.Y ("plus za {0}" -f $player.Label)
        Wait-Agent 1200
        Wait-ManualTeamRestAd $Handle $player.Label
    }

    [System.Media.SystemSounds]::Exclamation.Play()
    Set-Status 'Odmor ekipe je zavrsen.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
}

function Get-TVFlowSnapshot {
    param([IntPtr]$Handle)

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'tv_flow'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    return ($script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json)
}

function Wait-TVFlowState {
    param(
        [IntPtr]$Handle,
        [string[]]$ExpectedStates,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-TVFlowSnapshot $Handle
        if ([string]$snapshot.state -in $ExpectedStates) { return $snapshot }
        if (Try-RecoverConnectionInterruptedPopup $Handle) {
            $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))
            continue
        }
        Start-Sleep -Milliseconds 250
    }
    throw "TV ekran nije prepoznat: $($ExpectedStates -join ', ')."
}

function Watch-TVAdvertisement {
    param(
        [IntPtr]$Handle,
        [bool]$ManualReward,
        [ValidateSet('tv', 'mourinho', 'campus', 'put_saveza', 'training_player')]
        [string]$ReturnFlow = 'tv'
    )

    $adStartedAt = Get-Date
    $deadline = $adStartedAt.AddMinutes(5)
    $xDetectionStartsAt = $adStartedAt.AddSeconds($script:XDetectionDelaySeconds)
    $aiOnlyFallbackStartsAt = $adStartedAt.AddSeconds($script:VisionAiOnlyFallbackAfterSeconds)
    # Nema posebnog AI probea nakon 5 sekundi; prvi je puni redovni interval.
    $nextAiProbeAt = $adStartedAt.AddSeconds($script:VisionAiProbeIntervalSeconds)
    $aiExpectedState = "ad_control_ai_only_$($ReturnFlow)_$($adStartedAt.Ticks)"
    $aiOnlyLogged = $false
    $adObserved = $false
    $appReturnStableCount = 0
    $nextAdWakeTapAt = $adStartedAt.AddSeconds($script:AdWakeTapAfterSeconds)
    $adWakeBurstUntil = $null
    $adWakeTapCount = 0
    $flowLabel = switch ($ReturnFlow) {
        'mourinho' { 'Mourinho' }
        'campus' { 'Kampus' }
        'put_saveza' { 'Put saveza' }
        'training_player' { 'Trening igraca' }
        default { 'TV' }
    }

    Set-Status "$flowLabel reklama je pokrenuta; nadgledam X, skip i Google Play..."
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled

        # Store/Chrome mora imati prioritet nad bilo kakvim vizuelnim stanjem.
        # Time TV recognizer ne moze pogresno proglasiti Store povratkom u igru.
        if (Restore-AdFromGooglePlay $Handle $adStartedAt) {
            $adObserved = $true
            Start-Sleep -Milliseconds 100
            continue
        }

        $topElevenMainActive = Test-TopElevenReturnedAfterAd $Handle $adStartedAt
        $currentForeground = Get-BlueStacksForegroundState
        $currentIsMainActivity = $null -ne $currentForeground -and
            $currentForeground.Package -eq 'eu.nordeus.topeleven.android' -and
            $currentForeground.Activity -eq 'eu.nordeus.common.MainPlayerNativeActivity'
        $currentForegroundIsFresh = $null -ne $currentForeground -and
            $null -ne $currentForeground.EventTime -and
            $currentForeground.EventTime -ge $adStartedAt.AddSeconds(-1)
        $currentShowsAdOrExternal = $currentForegroundIsFresh -and (
            $currentForeground.Package -eq 'com.android.vending' -or
            $currentForeground.Package -eq 'com.android.chrome' -or
            ($currentForeground.Package -eq 'eu.nordeus.topeleven.android' -and
                $currentForeground.Activity -ne 'eu.nordeus.common.MainPlayerNativeActivity')
        )
        if ($ReturnFlow -ne 'tv') {
            if ($topElevenMainActive) {
                if ($adObserved -and ((Get-Date) - $adStartedAt).TotalSeconds -ge 3) {
                    $appReturnStableCount++
                    if ($appReturnStableCount -eq 1) {
                        Add-Log 'Top Eleven glavna Android aktivnost je pronadjena; potvrdjujem povratak...'
                    }
                    if ($appReturnStableCount -ge 3) {
                        Add-Log 'Povratak u Top Eleven potvrdjen je preko MainPlayerNativeActivity.'
                        return 'top_eleven'
                    }
                }
            }
            else {
                $appReturnStableCount = 0
                if ($currentShowsAdOrExternal) { $adObserved = $true }
            }
        }
        else {
            if (-not $topElevenMainActive) {
                if ($currentShowsAdOrExternal) { $adObserved = $true }
            }
            elseif ($adObserved) {
                # OpenCV se ovdje koristi samo za razlikovanje internih TV/prirucnik
                # ekrana, nikada za X, skip ili Google Play dugme reklame.
                $flowSnapshot = Get-TVFlowSnapshot $Handle
                $flowState = [string]$flowSnapshot.state
                if ($flowState -eq 'manual_3') {
                    Add-Log 'Povratak iz reklame na ekran novog prirucnika je potvrdjen.'
                    return 'manual_3'
                }
                if ($flowState -eq 'tv' -and ((Get-Date) - $adStartedAt).TotalSeconds -ge 3) {
                    Add-Log 'Povratak iz reklame na Top Eleven TV je potvrdjen.'
                    return 'tv'
                }
            }
        }

        if ((Get-Date) -ge $nextAdWakeTapAt -and $adWakeTapCount -lt $script:AdWakeTapMaximum) {
            $adWakeTapCount++
            Set-Status "$flowLabel reklama dugo traje - dodirujem ekran da ponovo prikazem kratku kontrolu..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            Click-Relative $Handle 0.500 0.620 "$flowLabel reklama - probudi skrivenu kontrolu"
            $adWakeBurstUntil = (Get-Date).AddSeconds($script:AdWakeBurstSeconds)
            $nextAdWakeTapAt = (Get-Date).AddSeconds($script:AdWakeTapIntervalSeconds)
            $script:VisionCacheByState.Remove($aiExpectedState)
            $nextAiProbeAt = Get-Date
            Add-Log "Wake provjera $adWakeTapCount/$script:AdWakeTapMaximum`: AI provjera krece odmah."
        }
        $wakeBurstActive = $null -ne $adWakeBurstUntil -and (Get-Date) -lt $adWakeBurstUntil
        $aiOnlyFallbackActive = $false
        if ($aiOnlyFallbackActive -and -not $aiOnlyLogged) {
            $aiOnlyLogged = $true
            Set-Status "$flowLabel reklama je i dalje otvorena nakon 60 sekundi - koristim samo AI provjeru." ([System.Drawing.Color]::FromArgb(255, 210, 100))
        }

        if ($script:VisionEnabled -and (Get-Date) -ge $nextAiProbeAt) {
            $nextAiProbeAt = (Get-Date).AddSeconds($script:VisionAiProbeIntervalSeconds)
            Add-Log "AI periodicna provjera $flowLabel reklame..."
            $aiControlReady = Test-AiOnlyAdControlReady $Handle $aiExpectedState
            if ($script:AiAdVisible) { $adObserved = $true }
            if ($script:AiTopElevenReturned -and $adObserved) {
                if ($ReturnFlow -ne 'tv') {
                    Add-Log "Povratak iz $flowLabel reklame potvrden je AI analizom Top Eleven zaglavlja."
                    return 'top_eleven'
                }

                # AI potvrduje da je igra vracena; interni recognizer samo razlikuje
                # TV ekran od ekrana novog prirucnika i ne bira reklamna dugmad.
                $returnedFlow = Get-TVFlowSnapshot $Handle
                if ([string]$returnedFlow.state -eq 'manual_3') {
                    Add-Log 'AI je potvrdio igru, a ekran novog prirucnika je prepoznat.'
                    return 'manual_3'
                }
                if ([string]$returnedFlow.state -eq 'tv') {
                    Add-Log 'AI je potvrdio povratak na Top Eleven TV.'
                    return 'tv'
                }
                Add-Log 'AI vidi Top Eleven, ali TV pod-ekran jos nije stabilan; nastavljam provjeru.'
                continue
            }
            if ($script:AiTopElevenReturned -and -not $adObserved) {
                Add-Log 'AI jos vidi pocetni Top Eleven ekran, ali reklama nije bila opazena; cekam stvarni reklamni tok.'
            }
            if ($aiControlReady) {
                $kind = $script:DetectedAdCloseKind
                if ($kind -eq 'close') {
                    $preClickState = Confirm-AiAdCloseImmediatelyBeforeClick $Handle "$flowLabel reklama"
                    if ($preClickState -eq 'returned') {
                        if ($ReturnFlow -ne 'tv') { return 'top_eleven' }
                        $returnedFlow = Get-TVFlowSnapshot $Handle
                        if ([string]$returnedFlow.state -eq 'manual_3') { return 'manual_3' }
                        if ([string]$returnedFlow.state -eq 'tv') { return 'tv' }
                        continue
                    }
                    if ($preClickState -ne 'close') {
                        $nextAiProbeAt = Get-Date
                        continue
                    }
                }
                $label = if ($kind -eq 'google_play') { "Google Play - $flowLabel AI" } elseif ($kind -eq 'skip') { "Skip - $flowLabel AI" } else { "X - $flowLabel AI" }
                if ($kind -eq 'google_play') { $script:LastGooglePlayClickAt = Get-Date }
                Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY $label
                Wait-Agent $script:TransitionBufferMs
                if ($kind -eq 'google_play') {
                    Restore-AdFromGooglePlay $Handle $adStartedAt | Out-Null
                }
                $aiExpectedState = "ad_control_ai_only_$($ReturnFlow)_$((Get-Date).Ticks)"
                if ($kind -eq 'close') {
                    $exitState = Wait-ForAdExitOrControl $Handle 10 $adStartedAt
                    if ($exitState -eq 'exited') {
                        if ($ReturnFlow -ne 'tv') {
                            Add-Log "Povratak iz $flowLabel reklame potvrden je odmah nakon X-a."
                            return 'top_eleven'
                        }
                        $returnedFlow = Get-TVFlowSnapshot $Handle
                        if ([string]$returnedFlow.state -eq 'manual_3') { return 'manual_3' }
                        if ([string]$returnedFlow.state -eq 'tv') { return 'tv' }
                    }
                    # Ako se prikazala nova kontrola ili TV ekran jos nije stabilan,
                    # odmah napravi novu AI provjeru umjesto cekanja redovnog intervala.
                    $script:VisionCacheByState.Remove($aiExpectedState)
                    $nextAiProbeAt = Get-Date
                }
                continue
            }
        }

        if ($aiOnlyFallbackActive) {
            Start-Sleep -Milliseconds 100
            continue
        }

        if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt -and (Test-YellowAdControlReady $Handle)) {
            $kind = $script:DetectedYellowControlKind
            Click-Relative $Handle $script:DetectedYellowControlX $script:DetectedYellowControlY ("{0} kontrola - {1}" -f $flowLabel, $kind)
            Wait-Agent $script:TransitionBufferMs
            if ($kind -eq 'google_play') {
                Restore-AdFromGooglePlay $Handle $adStartedAt | Out-Null
            }
            continue
        }

        if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt -and (Test-AdCloseReady $Handle)) {
            Click-Relative $Handle $script:DetectedAdCloseX $script:DetectedAdCloseY ("{0} reklama - {1}" -f $flowLabel, $script:DetectedAdCloseKind)
            Wait-Agent $script:TransitionBufferMs
            $script:XDetectorStableCount = 0
            $script:XDetectorStableSince = $null
            continue
        }

        Start-Sleep -Milliseconds 100
    }

    throw "$flowLabel reklama nije zavrsena u roku od 5 minuta."
}

function Complete-TVManualReward {
    param([IntPtr]$Handle)

    Wait-TVFlowState $Handle @('manual_3') 20 | Out-Null
    Set-Status 'Prirucnik je dobijen - prvi dodir ekrana...'
    Click-Relative $Handle 0.500 0.550 'Prirucnik - otkrij vjezbu'
    Wait-Agent $script:TVClickBufferMs
    Wait-TVFlowState $Handle @('manual_4') 20 | Out-Null

    Set-Status 'Vjezba je otkrivena - drugi dodir ekrana...'
    Click-Relative $Handle 0.500 0.550 'Prirucnik - potvrdi vjezbu'
    Wait-Agent $script:TVClickBufferMs
    $continueSnapshot = Wait-TVFlowState $Handle @('manual_5') 20

    Set-Status 'Prirucnik je zavrsen - pritiskam NASTAVI.'
    if ($null -ne $continueSnapshot.continueButton) {
        Click-Relative $Handle ([double]$continueSnapshot.continueButton.x) ([double]$continueSnapshot.continueButton.y) 'NASTAVI - dinamicki detektor'
    }
    else {
        Add-Log 'Dinamicki NASTAVI nije pronadjen; koristim postojecu referentnu lokaciju.'
        Click-Relative $Handle 0.382 0.936 'NASTAVI - referentna lokacija'
    }
    Wait-Agent $script:TVClickBufferMs
    Wait-TVFlowState $Handle @('tv') 25 | Out-Null
}

function Run-TVAutomation {
    param([IntPtr]$Handle)

    Set-Status 'Vracam TV tok na Pocetni ekran...'
    Click-GameRelative $Handle 0.014 0.068 'bocni meni - TV tok'
    Wait-Agent $script:TVNavigationBufferMs
    Click-GameRelative $Handle 0.125 0.040 'Pocetni - TV tok'
    Wait-Agent $script:TVNavigationBufferMs

    Set-Status 'Provjeravam pocetni ekran za TV tok...'
    $homeSnapshot = Wait-TVFlowState $Handle @('home') 20
    if ($null -eq $homeSnapshot.tvButton) {
        throw 'Pocetni ekran je prepoznat, ali TV dugme nije vizuelno pronadjeno.'
    }
    Click-Relative $Handle ([double]$homeSnapshot.tvButton.x) ([double]$homeSnapshot.tvButton.y) 'TV ikona - dinamicka lokacija'
    Wait-Agent $script:TVClickBufferMs
    Wait-TVFlowState $Handle @('tv') 25 | Out-Null
    Add-Log 'Top Eleven TV ekran je otvoren.'

    $watched = 0
    $noWatchButtonSince = $null
    $waitingForButtonLogged = $false
    while ($watched -lt 25) {
        Test-Cancelled
        $snapshot = Get-TVFlowSnapshot $Handle
        if ([string]$snapshot.state -ne 'tv') {
            $snapshot = Wait-TVFlowState $Handle @('tv') 20
        }
        $buttons = @($snapshot.buttons)
        if ($buttons.Count -eq 0) {
            if ($null -eq $noWatchButtonSince) {
                $noWatchButtonSince = Get-Date
                $waitingForButtonLogged = $false
            }
            if (-not $waitingForButtonLogged) {
                $waitingForButtonLogged = $true
                Set-Status "Trenutno nema potvrdjenog POGLEDAJ dugmeta - cekam najmanje $script:TVWatchButtonWaitSeconds sekundi da se TV ekran ucita/osvjezi..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            }
            $withoutButtonSeconds = ((Get-Date) - $noWatchButtonSince).TotalSeconds
            if ($withoutButtonSeconds -ge $script:TVWatchButtonWaitSeconds) {
                Set-Status "Nema vise dostupnih POGLEDAJ dugmadi. Pogledano: $watched reklama." ([System.Drawing.Color]::FromArgb(120, 240, 150))
                [System.Media.SystemSounds]::Exclamation.Play()
                return
            }
            Wait-Agent 1000
            continue
        }
        $noWatchButtonSince = $null
        $waitingForButtonLogged = $false

        $button = $buttons | Select-Object -First 1
        $manualReward = [bool]$button.manual
        $rewardLabel = if ($manualReward) { 'PRIRUCNIK' } else { 'TV nagrada' }
        Set-Status "POGLEDAJ je dostupno za $rewardLabel - pokrecem reklamu." ([System.Drawing.Color]::FromArgb(120, 240, 150))
        Click-Relative $Handle ([double]$button.x) ([double]$button.y) ("POGLEDAJ - {0}" -f $rewardLabel)
        Wait-Agent $script:TVClickBufferMs
        $returnState = Watch-TVAdvertisement $Handle $manualReward
        $watched++

        if ($manualReward -or $returnState -eq 'manual_3') {
            Complete-TVManualReward $Handle
        }
        else {
            Wait-TVFlowState $Handle @('tv') 20 | Out-Null
        }
        Wait-Agent $script:TVClickBufferMs
    }

    throw 'TV sigurnosni limit od 25 reklama je dostignut.'
}

function Get-MourinhoFlowSnapshot {
    param([IntPtr]$Handle)

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'mourinho_flow'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    return ($script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json)
}

function Wait-MourinhoFlowState {
    param(
        [IntPtr]$Handle,
        [string[]]$ExpectedStates,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-MourinhoFlowSnapshot $Handle
        if ([string]$snapshot.state -in $ExpectedStates) { return $snapshot }
        if (Try-RecoverConnectionInterruptedPopup $Handle) {
            $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))
            continue
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Mourinho ekran nije prepoznat: $($ExpectedStates -join ', ')."
}

function Run-MourinhoAutomation {
    param([IntPtr]$Handle)

    Set-Status 'AI trazi kvadratno dugme desno od readiness progress bara...'
    $warningTarget = $null
    for ($attempt = 1; $attempt -le 3 -and $null -eq $warningTarget; $attempt++) {
        Test-Cancelled
        Add-Log "Saljem AI-u sliku za Mourinho dugme (pokusaj $attempt/3)..."
        $warningTarget = Get-AiMourinhoWarning $Handle
        if ($null -eq $warningTarget -and $attempt -lt 3) {
            Wait-Agent 3000
        }
    }
    if ($null -eq $warningTarget) {
        throw 'AI nije pronasao kvadratno Mourinho dugme desno od readiness bara i lijevo od PREGLED UTAKMICE.'
    }

    Click-Relative $Handle $warningTarget.x $warningTarget.y 'Mourinho dugme - AI lokacija'
    Wait-Agent $script:TVClickBufferMs
    Wait-MourinhoFlowState $Handle @('mourinho_popup') 20 | Out-Null
    Add-Log 'Mourinho prozor je otvoren.'

    $waitStartedAt = Get-Date
    $button = $null
    Set-Status "Cekam potvrdeno plavo POGLEDAJ dugme s tekstom (do $script:TVWatchButtonWaitSeconds sekundi)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
    while (((Get-Date) - $waitStartedAt).TotalSeconds -lt $script:TVWatchButtonWaitSeconds) {
        Test-Cancelled
        $snapshot = Get-MourinhoFlowSnapshot $Handle
        if ([string]$snapshot.state -eq 'mourinho_popup' -and $null -ne $snapshot.button) {
            $button = $snapshot.button
            break
        }
        Wait-Agent 1000
    }

    if ($null -eq $button) {
        Set-Status "POGLEDAJ se nije pojavilo tokom $script:TVWatchButtonWaitSeconds sekundi; nista nije kliknuto." ([System.Drawing.Color]::FromArgb(255, 210, 100))
        return
    }

    Set-Status 'POGLEDAJ je potvrdeno po boji i tekstu - pokrecem reklamu.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
    Click-Relative $Handle ([double]$button.x) ([double]$button.y) 'POGLEDAJ - Mourinho'
    Wait-Agent $script:TVClickBufferMs
    Watch-TVAdvertisement $Handle $false 'mourinho' | Out-Null

    [System.Media.SystemSounds]::Exclamation.Play()
    Set-Status 'Povratak u Top Eleven je potvrdjen; Mourinho reklama je zavrsena.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
}

function Get-PutSavezaFlowSnapshot {
    param([IntPtr]$Handle)

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'alliance_flow'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    return ($script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json)
}

function Wait-PutSavezaFlowState {
    param(
        [IntPtr]$Handle,
        [string[]]$ExpectedStates,
        [int]$TimeoutSeconds = 25
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-PutSavezaFlowSnapshot $Handle
        if ([string]$snapshot.state -in $ExpectedStates) { return $snapshot }
        if (Try-RecoverConnectionInterruptedPopup $Handle) {
            $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))
            continue
        }
        Wait-Agent 250
    }
    throw "Put saveza ekran nije prepoznat: $($ExpectedStates -join ', ')."
}

function Scroll-SideMenu {
    param(
        [IntPtr]$Handle,
        [ValidateSet('Up', 'Down')]
        [string]$Direction,
        [int]$Steps = $script:PutSavezaMenuScrollSteps
    )

    $rect = Get-GameViewportRectangle $Handle
    $x = [int]($rect.Left + (($rect.Right - $rect.Left) * 0.12))
    $y = [int]($rect.Top + (($rect.Bottom - $rect.Top) * 0.55))
    if ($script:DryRun) {
        Add-Log "DRY RUN bocni meni: scroll $Direction na ($x, $y)"
        return
    }

    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    [Win32Agent]::SetCursorPos($x, $y) | Out-Null
    Wait-Agent 50
    for ($step = 1; $step -le [Math]::Max(1, $Steps); $step++) {
        if ($Direction -eq 'Down') {
            $wheelDown = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int]-120), 0)
            [Win32Agent]::mouse_event(0x0800, 0, 0, $wheelDown, [UIntPtr]::Zero)
        }
        else {
            [Win32Agent]::mouse_event(0x0800, 0, 0, 120, [UIntPtr]::Zero)
        }
        Wait-Agent 90
    }
    Wait-Agent 700
    Add-Log "Bocni meni: scroll $Direction ($Steps koraka)"
}

function Open-DynamicSideMenu {
    param(
        [IntPtr]$Handle,
        [string]$Purpose
    )

    $snapshot = Get-PutSavezaFlowSnapshot $Handle
    if ([string]$snapshot.state -eq 'side_menu') { return $snapshot }

    if ($null -ne $snapshot.menuToggle) {
        Click-Relative $Handle ([double]$snapshot.menuToggle.x) ([double]$snapshot.menuToggle.y) "bocni meni - $Purpose - dinamicki"
    }
    else {
        Add-Log "Dinamicki chevron za $Purpose nije pronadjen; koristim poznatu zonu lijevog taba."
        Click-GameRelative $Handle 0.014 0.068 "bocni meni - $Purpose"
    }
    Wait-Agent $script:TVNavigationBufferMs
    return (Wait-PutSavezaFlowState $Handle @('side_menu') 15)
}

function Find-SideMenuTarget {
    param(
        [IntPtr]$Handle,
        [ValidateSet('homeButton', 'campusButton', 'allianceButton')]
        [string]$TargetProperty,
        [ValidateSet('Up', 'Down')]
        [string]$Direction,
        [string]$Label,
        [int]$MaximumScrollActions = $script:PutSavezaMenuScrollAttempts,
        [int]$ScrollStepsPerAction = $script:PutSavezaMenuScrollSteps
    )

    for ($attempt = 0; $attempt -le $MaximumScrollActions; $attempt++) {
        Test-Cancelled
        $snapshot = Get-PutSavezaFlowSnapshot $Handle
        $target = $snapshot.$TargetProperty
        if ([string]$snapshot.state -eq 'side_menu' -and $null -ne $target) {
            Add-Log "$Label je pronadjen u bocnom meniju nakon $attempt scroll akcija."
            return $target
        }
        if ($attempt -lt $MaximumScrollActions) {
            Scroll-SideMenu $Handle $Direction $ScrollStepsPerAction
        }
    }
    throw "$Label nije pronadjen u bocnom meniju nakon $MaximumScrollActions scroll akcija."
}

function Wait-PutSavezaPathButton {
    param(
        [IntPtr]$Handle,
        [int]$TimeoutSeconds = 35
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    Set-Status 'Savezi ekran se ucitava - cekam stvarnu PUT SAVEZA plocicu...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-PutSavezaFlowSnapshot $Handle
        if ([string]$snapshot.state -eq 'alliance' -and $null -ne $snapshot.pathButton) {
            return $snapshot.pathButton
        }
        Wait-Agent 500
    }
    throw "PUT SAVEZA plocica nije postala dostupna tokom $TimeoutSeconds sekundi."
}

function Wait-PutSavezaAdDecision {
    param([IntPtr]$Handle)

    $deadline = (Get-Date).AddSeconds($script:PutSavezaAdButtonWaitSeconds)
    # Ref6 raspored moze potvrditi zavrsetak ranije. Genericki ucitani grid
    # radi i kada je ostalo malo taskova, ali namjerno ceka duze i vise frameova.
    $exactCompleteDecisionStartsAt = (Get-Date).AddSeconds(15)
    # IDI timeout je 30 s; fallback za vec zavrsen dnevni zadatak mora postati
    # dostupan ranije kako bi stalo pet stabilnih potvrda prije isteka roka.
    $genericCompleteDecisionStartsAt = (Get-Date).AddSeconds(20)
    $readyStableCount = 0
    $completeStableCount = 0
    $lastReadyX = $null
    $lastReadyY = $null
    $waitingLogged = $false

    Set-Status "Cekam stvarno plavo video dugme IDI (do $script:PutSavezaAdButtonWaitSeconds sekundi)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-PutSavezaFlowSnapshot $Handle
        if ([string]$snapshot.state -ne 'path') {
            $readyStableCount = 0
            $completeStableCount = 0
            Wait-Agent 400
            continue
        }

        if ($null -ne $snapshot.goButton) {
            $buttonX = [double]$snapshot.goButton.x
            $buttonY = [double]$snapshot.goButton.y
            $sameButton = $null -ne $lastReadyX -and
                [Math]::Abs($buttonX - $lastReadyX) -le 0.012 -and
                [Math]::Abs($buttonY - $lastReadyY) -le 0.012
            $readyStableCount = if ($sameButton) { $readyStableCount + 1 } else { 1 }
            $lastReadyX = $buttonX
            $lastReadyY = $buttonY
            $completeStableCount = 0
            if ($readyStableCount -ge 2) {
                return [PSCustomObject]@{
                    Outcome = 'ready'
                    Button = $snapshot.goButton
                    Snapshot = $snapshot
                }
            }
        }
        else {
            $readyStableCount = 0
            $lastReadyX = $null
            $lastReadyY = $null
            if ([bool]$snapshot.dailyTaskPresent) {
                $completeStableCount = 0
                if (-not $waitingLogged) {
                    $waitingLogged = $true
                    Add-Log 'DNEVNA Video Master kartica je vidljiva, ali tacni plavi video-IDI glyph jos nije spreman.'
                }
            }
            else {
                $exactCompleted = (Get-Date) -ge $exactCompleteDecisionStartsAt -and [bool]$snapshot.completedLayout
                $genericCompleted = (Get-Date) -ge $genericCompleteDecisionStartsAt -and [bool]$snapshot.taskGridLoaded
                if (($exactCompleted -or $genericCompleted) -and
                    $null -eq $snapshot.goButtonVisible -and
                    $null -ne $snapshot.closeButton) {
                    $completeStableCount++
                    $requiredCompleteFrames = if ($exactCompleted) { 2 } else { 5 }
                    if ($completeStableCount -ge $requiredCompleteFrames) {
                        return [PSCustomObject]@{
                            Outcome = 'already_complete'
                            Button = $null
                            Snapshot = $snapshot
                        }
                    }
                }
                else {
                    $completeStableCount = 0
                }
            }
        }
        Wait-Agent 400
    }
    throw "Plavo video dugme IDI nije postalo dostupno tokom $script:PutSavezaAdButtonWaitSeconds sekundi."
}

function Wait-PutSavezaStableCloseButton {
    param(
        [IntPtr]$Handle,
        [int]$TimeoutSeconds = 35
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $stableCount = 0
    $lastX = $null
    $lastY = $null
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-PutSavezaFlowSnapshot $Handle
        if ([string]$snapshot.state -eq 'path' -and $null -ne $snapshot.closeButton) {
            $x = [double]$snapshot.closeButton.x
            $y = [double]$snapshot.closeButton.y
            $same = $null -ne $lastX -and
                [Math]::Abs($x - $lastX) -le 0.012 -and
                [Math]::Abs($y - $lastY) -le 0.012
            $stableCount = if ($same) { $stableCount + 1 } else { 1 }
            $lastX = $x
            $lastY = $y
            if ($stableCount -ge 2) { return $snapshot.closeButton }
        }
        else {
            $stableCount = 0
            $lastX = $null
            $lastY = $null
        }
        Wait-Agent 350
    }
    throw 'Put saveza modalni X nije stabilno pronadjen nakon povratka iz reklame.'
}

function Close-PutSavezaModal {
    param([IntPtr]$Handle)

    $closeButton = Wait-PutSavezaStableCloseButton $Handle
    Click-Relative $Handle ([double]$closeButton.x) ([double]$closeButton.y) 'Put saveza - modalni X'
    Wait-Agent $script:TVNavigationBufferMs
    Wait-PutSavezaFlowState $Handle @('alliance') 25 | Out-Null
}

function Run-PutSavezaAutomation {
    param([IntPtr]$Handle)

    $formWasTopMost = $form.TopMost
    $form.TopMost = $false
    try {
        [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
        Set-Status 'Otvaram bocni meni i odmah skrolam prema Savezi...'
        Open-DynamicSideMenu $Handle 'Put saveza - Savezi' | Out-Null
        # Na standardnom meniju Savezi postane vidljiv nakon tacno jednog
        # wheel koraka prema dolje. Ne ponavljaj scroll jer bi meni nepotrebno
        # nastavio bjezati od trazenog reda.
        $allianceButton = Find-SideMenuTarget $Handle 'allianceButton' 'Down' 'Savezi' 1 1
        Click-Relative $Handle ([double]$allianceButton.x) ([double]$allianceButton.y) 'Savezi - bocni meni'
        Wait-Agent $script:TVNavigationBufferMs

        $pathButton = Wait-PutSavezaPathButton $Handle
        Set-Status 'Savezi ekran je otvoren - pritiskam PUT SAVEZA.'
        Click-Relative $Handle ([double]$pathButton.x) ([double]$pathButton.y) 'PUT SAVEZA - dinamicka plocica'
        Wait-Agent $script:TVNavigationBufferMs
        Wait-PutSavezaFlowState $Handle @('path') 25 | Out-Null

        $decision = Wait-PutSavezaAdDecision $Handle
        if ([string]$decision.Outcome -eq 'already_complete') {
            Set-Status 'Dnevna Put saveza reklama je vec zavrsena - zatvaram Put saveza.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
            Close-PutSavezaModal $Handle
            return
        }

        # Posljednja svjeza provjera neposredno prije jednog klika.  Nikada se
        # ne koristi stara koordinata niti fallback pomak.
        Wait-Agent 400
        $fresh = Get-PutSavezaFlowSnapshot $Handle
        $stableButton = $decision.Button
        if ([string]$fresh.state -ne 'path' -or $null -eq $fresh.goButton -or
            [Math]::Abs(([double]$fresh.goButton.x) - ([double]$stableButton.x)) -gt 0.012 -or
            [Math]::Abs(([double]$fresh.goButton.y) - ([double]$stableButton.y)) -gt 0.012) {
            Add-Log 'Plavi IDI se promijenio prije klika; cekam novu stabilnu potvrdu.'
            $decision = Wait-PutSavezaAdDecision $Handle
            if ([string]$decision.Outcome -ne 'ready') {
                Set-Status 'Put saveza reklama vise nije dostupna - zatvaram zavrseni modal.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
                Close-PutSavezaModal $Handle
                return
            }
            Wait-Agent 400
            $fresh = Get-PutSavezaFlowSnapshot $Handle
            if ([string]$fresh.state -ne 'path' -or $null -eq $fresh.goButton -or
                [Math]::Abs(([double]$fresh.goButton.x) - ([double]$decision.Button.x)) -gt 0.012 -or
                [Math]::Abs(([double]$fresh.goButton.y) - ([double]$decision.Button.y)) -gt 0.012) {
                throw 'Plavo video dugme IDI nije ostalo stabilno do trenutka klika.'
            }
        }

        Set-Status 'Plavo video dugme IDI je stabilno potvrdeno - pokrecem reklamu.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
        Click-Relative $Handle ([double]$fresh.goButton.x) ([double]$fresh.goButton.y) 'Put saveza - plavi video IDI'
        Wait-Agent $script:TVClickBufferMs
        Watch-TVAdvertisement $Handle $false 'put_saveza' | Out-Null

        Set-Status 'Put saveza reklama je zavrsena - cekam modal i zatvaram ga tacnim X dugmetom.'
        Close-PutSavezaModal $Handle
        [System.Media.SystemSounds]::Exclamation.Play()
        Set-Status 'Put saveza faza je zavrsena.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
    }
    catch {
        $putSavezaFailure = $_
        try {
            $failureSnapshot = Get-PutSavezaFlowSnapshot $Handle
            if ([string]$failureSnapshot.state -eq 'path' -and $null -ne $failureSnapshot.closeButton) {
                Add-Log 'Put saveza faza je prekinuta unutar modala; sigurno ga zatvaram prije sljedece faze.'
                Close-PutSavezaModal $Handle
            }
        }
        catch {
            Add-Log "Put saveza cleanup nije potvrdjen: $($_.Exception.Message)"
        }
        throw $putSavezaFailure
    }
    finally {
        $form.TopMost = $formWasTopMost
    }
}

function Get-TrainingPlayerFlowSnapshot {
    param([IntPtr]$Handle)

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'training_player_flow'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    return ($script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json)
}

function Click-TrainingPlayerRelative {
    param(
        [IntPtr]$Handle,
        [double]$X,
        [double]$Y,
        [string]$Label
    )
    Click-Relative $Handle $X $Y $Label
    Wait-Agent $script:TrainingPlayerClickBufferMs
}

function Click-TrainingPlayerGameRelative {
    param(
        [IntPtr]$Handle,
        [double]$X,
        [double]$Y,
        [string]$Label
    )
    Click-GameRelative $Handle $X $Y $Label
    Wait-Agent $script:TrainingPlayerClickBufferMs
}

function Click-TrainingPlayerClose {
    param(
        [IntPtr]$Handle,
        [double]$X,
        [double]$Y,
        [string]$Label
    )
    Add-Log ("Cekam {0:N1}s prije sigurnog X klika: {1}." -f ($script:TrainingPlayerCloseBufferMs / 1000.0), $Label)
    Wait-Agent $script:TrainingPlayerCloseBufferMs
    Click-TrainingPlayerRelative $Handle $X $Y $Label
}

function Wait-TrainingPlayerState {
    param(
        [IntPtr]$Handle,
        [string[]]$ExpectedStates,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-TrainingPlayerFlowSnapshot $Handle
        if ([string]$snapshot.state -in $ExpectedStates) { return $snapshot }
        if (Try-RecoverConnectionInterruptedPopup $Handle) {
            $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))
            continue
        }
        Wait-Agent 300
    }
    throw "Trening igraca ekran nije prepoznat: $($ExpectedStates -join ', ')."
}

function Wait-TrainingFreeButton {
    param([IntPtr]$Handle, [int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $stableCount = 0
    $lastX = $null
    $lastY = $null
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-TrainingPlayerFlowSnapshot $Handle
        if ([string]$snapshot.state -ne 'condition_modal') {
            $stableCount = 0
            Wait-Agent 300
            continue
        }
        $button = $snapshot.freeButton
        $same = $null -ne $button -and [bool]$button.ready -and
            ($null -eq $lastX -or ([Math]::Abs(([double]$button.x) - $lastX) -le 0.015 -and
            [Math]::Abs(([double]$button.y) - $lastY) -le 0.015))
        if ($same) {
            $stableCount++
            $lastX = [double]$button.x
            $lastY = [double]$button.y
            if ($stableCount -ge 2) { return $button }
        }
        else {
            $stableCount = 0
            $lastX = $null
            $lastY = $null
        }
        Wait-Agent 400
    }
    throw 'BESPLATNO za kondiciju nije postalo dostupno sa punim tekstom.'
}

function Get-AiTrainingSetupCondition {
    param([IntPtr]$Handle, [int]$RecoveryAttempt = 0)

    $expectedState = "training_setup_condition_$((Get-Date).Ticks)"
    Set-Status 'AI cita stvarni FIT procenat sa ekrana pripreme treninga...'
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 150
    $vision = Invoke-VisionAnalysis $Handle $expectedState
    if ($null -eq $vision -or -not [bool]$vision.accepted -or
        [string]$vision.decision.screenType -ne 'top_eleven') {
        if ($RecoveryAttempt -lt 3 -and (Try-RecoverConnectionInterruptedPopup $Handle)) {
            Add-Log 'Popup je uklonjen tokom FIT provjere; ponavljam citanje procenata.'
            return Get-AiTrainingSetupCondition $Handle ($RecoveryAttempt + 1)
        }
        throw 'AI nije pouzdano procitao FIT procente; trening nece biti pokrenut.'
    }

    $action = [string]$vision.decision.recommendedAction
    $visibleText = [string]$vision.decision.visibleText
    if ($action -eq 'click_training_player' -and
        $visibleText -match '^\s*CONDITION\s*:\s*(\d{1,3})\s*%\s*$') {
        $condition = [int]$Matches[1]
        if ($condition -ge 30 -or $null -eq $vision.decision.control.x -or
            $null -eq $vision.decision.control.y) {
            throw 'AI rezultat za igraca ispod 30% nije prosao sigurnosnu provjeru.'
        }
        return [PSCustomObject]@{
            HasLow = $true
            Condition = $condition
            X = [double]$vision.decision.control.x
            Y = [double]$vision.decision.control.y
        }
    }
    if ($action -eq 'none' -and
        $visibleText -match '^\s*LOWEST_CONDITION\s*:\s*(\d{1,3})\s*%\s*$') {
        $condition = [int]$Matches[1]
        if ($condition -lt 30 -or $condition -gt 100) {
            throw 'AI procenat nije dovoljan za siguran pocetak treninga.'
        }
        return [PSCustomObject]@{ HasLow = $false; Condition = $condition; X = $null; Y = $null }
    }
    throw "AI nije vratio strogo citljiv FIT procenat: '$visibleText'."
}

function Get-AiTrainingProfileCondition {
    param([IntPtr]$Handle, [int]$RecoveryAttempt = 0)

    $expectedState = "training_profile_condition_$((Get-Date).Ticks)"
    Set-Status 'AI cita stvarni procenat KONDICIJE igraca...'
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 150
    $vision = Invoke-VisionAnalysis $Handle $expectedState
    $visibleText = if ($null -ne $vision) { [string]$vision.decision.visibleText } else { '' }
    if ($null -eq $vision -or -not [bool]$vision.accepted -or
        [string]$vision.decision.screenType -ne 'top_eleven' -or
        $visibleText -notmatch '^\s*CONDITION\s*:\s*(\d{1,3})\s*%\s*$') {
        if ($RecoveryAttempt -lt 3 -and (Try-RecoverConnectionInterruptedPopup $Handle)) {
            Add-Log 'Popup je uklonjen tokom provjere KONDICIJE; ponavljam citanje procenta.'
            return Get-AiTrainingProfileCondition $Handle ($RecoveryAttempt + 1)
        }
        throw 'AI nije pouzdano procitao procenat KONDICIJE; ne klikcem naslijepo.'
    }
    $condition = [int]$Matches[1]
    if ($condition -lt 0 -or $condition -gt 100) {
        throw 'AI je vratio neispravan procenat KONDICIJE.'
    }
    $action = [string]$vision.decision.recommendedAction
    if ($condition -lt 85) {
        if ($action -ne 'click_training_condition_plus' -or
            $null -eq $vision.decision.control.x -or $null -eq $vision.decision.control.y) {
            throw 'AI nije locirao zeleni + u KONDICIJA panelu.'
        }
        return [PSCustomObject]@{
            Condition = $condition
            HasPlus = $true
            X = [double]$vision.decision.control.x
            Y = [double]$vision.decision.control.y
        }
    }
    if ($action -ne 'click_training_player_close' -or
        $null -eq $vision.decision.control.x -or $null -eq $vision.decision.control.y) {
        throw 'AI je procitao najmanje 85%, ali nije locirao X profila igraca.'
    }
    return [PSCustomObject]@{
        Condition = $condition
        HasPlus = $false
        X = [double]$vision.decision.control.x
        Y = [double]$vision.decision.control.y
    }
}

function Restore-TrainingPlayerCondition {
    param([IntPtr]$Handle)

    for ($reward = 1; $reward -le 20; $reward++) {
        Test-Cancelled
        $detail = Wait-TrainingPlayerState $Handle @('player_detail', 'condition_modal') 30
        $profileDecision = Get-AiTrainingProfileCondition $Handle
        $condition = [int]$profileDecision.Condition
        Add-Log ("AI je procitao kondiciju igraca: {0}%." -f $condition)
        if ($condition -ge 85) {
            Add-Log ("Kondicija igraca je dostigla {0}% - zatvaram profil." -f $condition)
            if ([string]$detail.state -eq 'condition_modal') {
                Click-TrainingPlayerClose $Handle ([double]$detail.modalClose.x) ([double]$detail.modalClose.y) 'zatvori BESPLATNO modal'
                $detail = Wait-TrainingPlayerState $Handle @('player_detail') 15
            }
            Click-TrainingPlayerClose $Handle ([double]$profileDecision.X) ([double]$profileDecision.Y) 'X - profil igraca nakon najmanje 85% kondicije - AI'
            Wait-TrainingPlayerState $Handle @('setup') 25 | Out-Null
            return
        }

        if ([string]$detail.state -eq 'condition_modal') {
            Click-TrainingPlayerClose $Handle ([double]$detail.modalClose.x) ([double]$detail.modalClose.y) 'zatvori stari modal kondicije'
            Wait-TrainingPlayerState $Handle @('player_detail') 15 | Out-Null
            $detail = Get-TrainingPlayerFlowSnapshot $Handle
        }
        Set-Status ("AI je procitao {0}% kondicije - otvaram besplatni oporavak #{1}." -f $condition, $reward)
        if (-not [bool]$profileDecision.HasPlus) {
            throw 'AI nije potvrdio zeleni + za kondiciju.'
        }
        Click-TrainingPlayerRelative $Handle ([double]$profileDecision.X) ([double]$profileDecision.Y) 'zeleni + za kondiciju - AI'
        Wait-TrainingPlayerState $Handle @('condition_modal') 20 | Out-Null
        $freeButton = Wait-TrainingFreeButton $Handle 120

        # Posljednja svjeza provjera neposredno prije klika.
        $fresh = Get-TrainingPlayerFlowSnapshot $Handle
        if ([string]$fresh.state -ne 'condition_modal' -or $null -eq $fresh.freeButton -or -not [bool]$fresh.freeButton.ready) {
            Add-Log 'BESPLATNO se promijenilo prije klika; vracam se na stabilnu provjeru.'
            continue
        }
        Click-TrainingPlayerRelative $Handle ([double]$fresh.freeButton.x) ([double]$fresh.freeButton.y) 'BESPLATNO - kondicija igraca'
        Watch-TVAdvertisement $Handle $false 'training_player' | Out-Null
        Wait-Agent $script:TransitionBufferMs
    }
    throw 'Kondicija igraca nije dostigla 85% nakon 20 besplatnih oporavaka.'
}

function Run-TrainingPlayerAutomation {
    param([IntPtr]$Handle)

    $formWasTopMost = $form.TopMost
    $form.TopMost = $false
    try {
        Set-Status 'Otvaram bocni meni za Trening igraca...'
        [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
        Click-TrainingPlayerGameRelative $Handle 0.014 0.068 'bocni meni - Trening igraca'
        Click-TrainingPlayerGameRelative $Handle 0.087 0.189 'Trening - bocni meni'
        Wait-TrainingPlayerState $Handle @('training_home') 35 | Out-Null

        for ($cycle = 1; $cycle -le 100; $cycle++) {
            Test-Cancelled
            Set-Status "Trening igraca - ciklus $cycle`: otvaram IZVJESTAJI."
            $trainingHomeSnapshot = Get-TrainingPlayerFlowSnapshot $Handle
            if ([string]$trainingHomeSnapshot.state -ne 'training_home' -or $null -eq $trainingHomeSnapshot.reportsButton) {
                throw 'Dugme IZVJESTAJI nije dostupno na Trening ekranu.'
            }
            Click-TrainingPlayerRelative $Handle ([double]$trainingHomeSnapshot.reportsButton.x) ([double]$trainingHomeSnapshot.reportsButton.y) 'IZVJESTAJI'
            $reports = Wait-TrainingPlayerState $Handle @('reports') 25
            Click-TrainingPlayerRelative $Handle ([double]$reports.repeatButton.x) ([double]$reports.repeatButton.y) 'PONOVI - najnoviji trening'
            $setup = Wait-TrainingPlayerState $Handle @('setup') 25

            for ($conditionPass = 1; $conditionPass -le 30; $conditionPass++) {
                $conditionDecision = Get-AiTrainingSetupCondition $Handle
                if (-not [bool]$conditionDecision.HasLow) {
                    Add-Log ("AI je potvrdio da je najniza FIT kondicija {0}% i nijedan igrac nije ispod 30%." -f $conditionDecision.Condition)
                    break
                }
                Add-Log ("AI je procitao igraca ispod 30% kondicije: {0}%." -f $conditionDecision.Condition)
                Click-TrainingPlayerRelative $Handle ([double]$conditionDecision.X) ([double]$conditionDecision.Y) 'igrac ispod 30% kondicije - AI'
                Wait-TrainingPlayerState $Handle @('player_detail') 20 | Out-Null
                Restore-TrainingPlayerCondition $Handle
                $setup = Wait-TrainingPlayerState $Handle @('setup') 20
            }

            # Obavezna svjeza provjera neposredno prije nepovratnog klika.
            $setup = Get-TrainingPlayerFlowSnapshot $Handle
            if ([string]$setup.state -ne 'setup') {
                throw 'Ekran pripreme treninga se promijenio prije pokretanja.'
            }
            $freshConditionDecision = Get-AiTrainingSetupCondition $Handle
            if ([bool]$freshConditionDecision.HasLow) {
                throw ("Sigurnosna blokada: AI jos vidi igraca na {0}% kondicije." -f $freshConditionDecision.Condition)
            }

            Set-Status "Kondicija je spremna - pokrecem trening #$cycle."
            # Ovaj klik namjerno nema automatski 1.8s wrapper: nakon njega se
            # ceka jednu sekundu pa se trening jednom neutralno dodirne.
            Click-Relative $Handle ([double]$setup.startButton.x) ([double]$setup.startButton.y) 'ZAPOCNI TRENING'
            Wait-Agent 1000
            Click-TrainingPlayerRelative $Handle 0.500 0.720 'Trening - jedan dodir nakon 1 sekunde'
            $result = Wait-TrainingPlayerState $Handle @('training_result') 180
            Click-TrainingPlayerClose $Handle ([double]$result.closeButton.x) ([double]$result.closeButton.y) 'X - izvjestaj o treningu'
            Wait-TrainingPlayerState $Handle @('training_home') 35 | Out-Null
            Add-Log "Trening igraca #$cycle je zavrsen; pokrecem novi ciklus."
        }
        throw 'Dostignut je sigurnosni limit od 100 trening ciklusa.'
    }
    finally {
        $form.TopMost = $formWasTopMost
    }
}

function Get-CampusFlowSnapshot {
    param([IntPtr]$Handle)

    Start-XDetector
    $rect = Get-WindowRectangle $Handle
    $request = @{
        rect = @($rect.Left, $rect.Top, $rect.Right, $rect.Bottom)
        mode = 'campus_flow'
    } | ConvertTo-Json -Compress
    $script:XDetectorProcess.StandardInput.WriteLine($request)
    $script:XDetectorProcess.StandardInput.Flush()
    return ($script:XDetectorProcess.StandardOutput.ReadLine() | ConvertFrom-Json)
}

function Wait-CampusFlowState {
    param(
        [IntPtr]$Handle,
        [string[]]$ExpectedStates,
        [int]$TimeoutSeconds = 25
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-CampusFlowSnapshot $Handle
        if ([string]$snapshot.state -in $ExpectedStates) { return $snapshot }
        if (Try-RecoverConnectionInterruptedPopup $Handle) {
            $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))
            continue
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Kampus ekran nije prepoznat: $($ExpectedStates -join ', ')."
}

function Get-AiCampusBuilding {
    param(
        [IntPtr]$Handle,
        [string]$ExpectedState = 'campus_incomplete_building'
    )

    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 120
    $vision = Invoke-VisionAnalysis $Handle $ExpectedState
    if ($null -eq $vision -or -not $vision.accepted) {
        return [PSCustomObject]@{ Resolved = $false; Available = $false }
    }

    $action = [string]$vision.decision.recommendedAction
    $controlType = [string]$vision.decision.control.type
    if ($action -eq 'none' -and $controlType -eq 'none') {
        Add-Log 'AI potvrda: svi vidljivi Kampus objekti su na 100%.'
        return [PSCustomObject]@{ Resolved = $true; Available = $false }
    }
    if ([string]$vision.decision.screenType -ne 'top_eleven' -or
        $action -ne 'click_campus_building' -or
        $controlType -ne 'campus_building') {
        return [PSCustomObject]@{ Resolved = $false; Available = $false }
    }
    if ($null -eq $vision.coordinateGrounding -or -not [bool]$vision.coordinateGrounding.ok) {
        Add-Log 'Kampus AI koordinata nema potvrdeno poravnanje sa trenutnim polozajem kamere; ne klikcem.'
        return [PSCustomObject]@{ Resolved = $false; Available = $false }
    }

    $target = [PSCustomObject]@{
        Resolved = $true
        Available = $true
        x = [double]$vision.decision.control.x
        y = [double]$vision.decision.control.y
        confidence = [double]$vision.decision.control.confidence
        description = [string]$vision.decision.visibleText
        reason = [string]$vision.decision.reason
        canonicalTarget = [string]$vision.coordinateGrounding.target
        sourceCaptureAgeMs = [int]$vision.coordinateGrounding.sourceCaptureAgeMs
        groundingInliers = [int]$vision.coordinateGrounding.inliers
        groundingMedianError = [double]$vision.coordinateGrounding.medianError
    }
    Add-Log ("Kampus kamera poravnata: {0}; AI={1:N3},{2:N3} -> svjezi objekat={3:N3},{4:N3}; stara slika={5:N1}s; inliers={6}; median greska={7:N2}px" -f
        $target.canonicalTarget,
        [double]$vision.coordinateGrounding.aiX,
        [double]$vision.coordinateGrounding.aiY,
        $target.x,
        $target.y,
        ($target.sourceCaptureAgeMs / 1000.0),
        $target.groundingInliers,
        $target.groundingMedianError)
    Add-Log ("AI je izabrao Kampus objekat: {0}; confidence={1:N2}; centar={2:N3},{3:N3}" -f $target.description, $target.confidence, $target.x, $target.y)
    return $target
}

function Get-AiCampusToolButton {
    param([IntPtr]$Handle)

    $expectedState = "campus_tool_icon_$((Get-Date).Ticks)"
    $formWasTopMost = $form.TopMost
    $form.TopMost = $false
    try {
        [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
        Wait-Agent 150
        $vision = Invoke-VisionAnalysis $Handle $expectedState
        if ($null -eq $vision -or -not [bool]$vision.accepted -or
            [string]$vision.decision.screenType -ne 'top_eleven' -or
            [string]$vision.decision.recommendedAction -ne 'click_campus_tool' -or
            [string]$vision.decision.control.type -ne 'campus_tool' -or
            $null -eq $vision.decision.control.x -or $null -eq $vision.decision.control.y) {
            throw 'AI nije pouzdano pronasao lijevu Kampus ikonu alata.'
        }
        $button = [PSCustomObject]@{
            x = [double]$vision.decision.control.x
            y = [double]$vision.decision.control.y
            confidence = [double]$vision.decision.control.confidence
        }
        Add-Log ("AI je pronasao Kampus ikonu alata: confidence={0:N2}, centar={1:N3},{2:N3}" -f
            $button.confidence, $button.x, $button.y)
        return $button
    }
    finally {
        $form.TopMost = $formWasTopMost
    }
}

function Resolve-AiCampusBuilding {
    param(
        [IntPtr]$Handle,
        [string]$ScanState
    )

    $script:VisionCacheByState.Remove($ScanState)
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        Add-Log "AI provjerava Kampus objekte ispod 100% (potvrda $attempt/4)..."
        $candidate = Get-AiCampusBuilding $Handle $ScanState
        if ($candidate.Resolved) { return $candidate }
        if ($attempt -lt 4) { Wait-Agent 2200 }
    }
    return $null
}

function Wait-CampusDetailOpened {
    param(
        [IntPtr]$Handle,
        [int]$TimeoutSeconds = 8
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-CampusFlowSnapshot $Handle
        if ([string]$snapshot.state -eq 'campus_detail') { return $snapshot }
        Wait-Agent 300
    }
    return $null
}

function Wait-CampusRewardAreaVisible {
    param(
        [IntPtr]$Handle,
        [PSCustomObject]$InitialSnapshot,
        [int]$TimeoutSeconds = 8
    )

    $snapshot = $InitialSnapshot
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        if ([string]$snapshot.state -eq 'campus_detail') {
            if ($null -ne $snapshot.hundredButtonVisible -or $null -ne $snapshot.hundredButton) {
                return $snapshot
            }
        }
        elseif ([string]$snapshot.state -eq 'campus_maintenance') {
            return $null
        }
        Wait-Agent 300
        $snapshot = Get-CampusFlowSnapshot $Handle
    }
    return $null
}

function Open-CampusBuildingDetail {
    param(
        [IntPtr]$Handle,
        [PSCustomObject]$InitialSelection,
        [int]$ObjectNumber
    )

    $selection = $InitialSelection
    $failedCoordinates = @()
    for ($clickAttempt = 1; $clickAttempt -le $script:CampusBuildingClickAttempts; $clickAttempt++) {
        if ($clickAttempt -gt 1) {
            $avoidTokens = @(
                foreach ($failed in $failedCoordinates) {
                    $avoidX = [int][Math]::Round([double]$failed.x * 1000.0)
                    $avoidY = [int][Math]::Round([double]$failed.y * 1000.0)
                    "avoid_$($avoidX)_$($avoidY)"
                }
            )
            $retryState = "campus_incomplete_building_object_$($ObjectNumber)_retry_$($clickAttempt)_$($avoidTokens -join '_')_$((Get-Date).Ticks)"
            Set-Status "Prethodni Kampus klik nije otvorio objekat - AI ponovo skenira ($clickAttempt/$script:CampusBuildingClickAttempts)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            $freshSelection = Resolve-AiCampusBuilding $Handle $retryState
            if ($null -eq $freshSelection -or -not $freshSelection.Available) {
                Add-Log 'AI nije potvrdio novu sigurnu koordinatu; stara promasena koordinata se ne ponavlja.'
                continue
            }
            $selection = $freshSelection
        }

        $sameFailedTarget = @(
            $failedCoordinates | Where-Object {
                -not [string]::IsNullOrWhiteSpace([string]$_.target) -and
                [string]$_.target -eq [string]$selection.canonicalTarget
            }
        ).Count -gt 0
        if ($sameFailedTarget) {
            Add-Log ("AI je ponovo izabrao vec promaseni Kampus objekat {0}; ne ponavljam istu canonical tacku." -f [string]$selection.canonicalTarget)
            continue
        }

        $freshCampusGate = Get-CampusFlowSnapshot $Handle
        if ([string]$freshCampusGate.state -ne 'campus_maintenance' -or
            [int]$freshCampusGate.maintenanceBadgeCount -lt 3) {
            Add-Log ("Svjezi Kampus ekran vise nije potvrden kao maintenance (state={0}, badgeovi={1}); ne klikcem zastarjelu tacku." -f
                [string]$freshCampusGate.state, [int]$freshCampusGate.maintenanceBadgeCount)
            return $null
        }
        Set-Status "Klikcem AI-potvrdjeni Kampus objekat ($clickAttempt/$script:CampusBuildingClickAttempts)." ([System.Drawing.Color]::FromArgb(120, 240, 150))
        Add-Log ("Kampus klik {0}/{1}: {2}; centar={3:N3},{4:N3}" -f $clickAttempt, $script:CampusBuildingClickAttempts, $selection.description, $selection.x, $selection.y)
        Click-Relative $Handle $selection.x $selection.y 'Kampus objekat ispod 100% - AI'
        Wait-Agent $script:TVClickBufferMs

        $detail = Wait-CampusDetailOpened $Handle $script:CampusDetailOpenWaitSeconds
        $remainingState = $null
        if ($null -eq $detail) {
            $remainingState = Get-CampusFlowSnapshot $Handle
            if ([string]$remainingState.state -eq 'campus_detail') {
                $detail = $remainingState
            }
            elseif ([string]$remainingState.state -ne 'campus_maintenance') {
                Add-Log ("Kampus je u prijelaznom stanju={0}; cekam jos dvije sekunde i ne klikcem." -f [string]$remainingState.state)
                $detail = Wait-CampusDetailOpened $Handle 2
                if ($null -eq $detail) { $remainingState = Get-CampusFlowSnapshot $Handle }
            }
        }

        if ($null -ne $detail) {
            $rewardDetail = Wait-CampusRewardAreaVisible $Handle $detail ([Math]::Max(10, $script:CampusDetailOpenWaitSeconds))
            if ($null -ne $rewardDetail) {
                Add-Log "Kampus detalj za objekat ispod 100% je potvrden nakon klika $clickAttempt."
                return $rewardDetail
            }

            Add-Log 'Otvoren je Campus detalj bez plavog 100% reward podrucja; zatvaram pogresan objekat i biram novu AI tacku.'
            Click-Relative $Handle 0.720 0.125 'Kampus crna zona - zatvori pogresan detalj'
            Wait-Agent $script:TVNavigationBufferMs
            try {
                $remainingState = Wait-CampusFlowState $Handle @('campus_maintenance') 15
            }
            catch {
                Add-Log 'Pogresan Campus detalj nije sigurno zatvoren; ne pokusavam novi klik.'
                return $null
            }
        }

        if ($null -ne $remainingState -and
            [string]$remainingState.state -eq 'campus' -and
            $null -ne $remainingState.toolButton) {
            Add-Log 'Kampus maintenance prikaz se zatvorio nakon promasenog klika; ponovo otvaram alat prije svjezeg AI retryja.'
            Click-Relative $Handle ([double]$remainingState.toolButton.x) ([double]$remainingState.toolButton.y) 'Kampus alat - oporavak nakon promasenog klika'
            Wait-Agent $script:TVNavigationBufferMs
            try {
                $remainingState = Wait-CampusFlowState $Handle @('campus_maintenance') 15
            }
            catch {
                Add-Log 'Kampus maintenance ekran nije sigurno vracen; ne pokusavam novi objekat.'
                return $null
            }
        }

        if ($null -eq $remainingState -or [string]$remainingState.state -ne 'campus_maintenance') {
            $remainingStateName = if ($null -eq $remainingState) { 'null' } else { [string]$remainingState.state }
            Add-Log ("Kampus stanje={0} nije sigurno za novi klik; prekidam retry bez klikanja." -f $remainingStateName)
            return $null
        }
        $failedCoordinates += [PSCustomObject]@{
            x = [double]$selection.x
            y = [double]$selection.y
            target = [string]$selection.canonicalTarget
        }
        Add-Log 'Kampus detalj nije otvoren i potvrdeno je da je maintenance ekran ostao otvoren.'
    }
    return $null
}

function Wait-CampusHundredButton {
    param([IntPtr]$Handle)

    $deadline = (Get-Date).AddSeconds($script:CampusHundredButtonWaitSeconds)
    Set-Status "Cekam da plavo dugme prikaze stvarni tekst 100% (do $script:CampusHundredButtonWaitSeconds sekundi)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $snapshot = Get-CampusFlowSnapshot $Handle
        if ([string]$snapshot.state -eq 'campus_detail' -and $null -ne $snapshot.hundredButton) {
            return $snapshot.hundredButton
        }
        Wait-Agent 1000
    }
    throw "Kampus dugme sa tekstom 100% nije postalo dostupno tokom $script:CampusHundredButtonWaitSeconds sekundi."
}

function Run-CampusAutomation {
    param([IntPtr]$Handle)

    Set-Status 'Otvaram bocni meni za Kampus tok...'
    Open-DynamicSideMenu $Handle 'Kampus tok' | Out-Null
    $campusButton = Find-SideMenuTarget $Handle 'campusButton' 'Up' 'Kampus'
    Click-Relative $Handle ([double]$campusButton.x) ([double]$campusButton.y) 'Kampus - dinamicki red bocnog menija'
    Set-Status "Kampus se ucitava - cekam sigurnosnih $([Math]::Round($script:CampusOpenBufferMs / 1000.0)) sekundi..."
    Wait-Agent $script:CampusOpenBufferMs

    Set-Status 'AI trazi lijevu Kampus ikonu alata na svjezoj slici...'
    $campusToolButton = Get-AiCampusToolButton $Handle
    Set-Status 'AI je pronasao Kampus ikonu alata - pritiskam njen centar.'
    Click-Relative $Handle ([double]$campusToolButton.x) ([double]$campusToolButton.y) 'Kampus alat - AI'
    Wait-Agent $script:TVNavigationBufferMs
    Wait-CampusFlowState $Handle @('campus_maintenance') 25 | Out-Null

    for ($objectNumber = 1; $objectNumber -le 12; $objectNumber++) {
        Test-Cancelled
        $formWasTopMost = $form.TopMost
        $form.TopMost = $false
        try {
            [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
            Wait-Agent 150
            $scanState = "campus_incomplete_building_object_$($objectNumber)_$((Get-Date).Ticks)"
            $selection = Resolve-AiCampusBuilding $Handle $scanState
            if ($null -eq $selection) {
                throw 'AI nije uspio vratiti siguran Kampus kandidat nakon cetiri svjeza skeniranja.'
            }
            if (-not $selection.Available) {
                [System.Media.SystemSounds]::Exclamation.Play()
                Set-Status "Kampus je zavrsen. Obradjeno objekata: $($objectNumber - 1)." ([System.Drawing.Color]::FromArgb(120, 240, 150))
                return
            }

            $campusDetail = Open-CampusBuildingDetail $Handle $selection $objectNumber
            if ($null -eq $campusDetail) {
                throw 'Kampus objekat nije otvoren; dodatni klikovi su sigurnosno prekinuti jer svjezi ekran ili koordinata nisu potvrdeni.'
            }
        }
        finally {
            $form.TopMost = $formWasTopMost
        }

        $hundredButton = Wait-CampusHundredButton $Handle
        Set-Status 'Dugme sa tekstom 100% je dostupno - pokrecem reklamu.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
        Click-Relative $Handle ([double]$hundredButton.x) ([double]$hundredButton.y) 'Kampus 100%'
        Wait-Agent $script:TVClickBufferMs
        Watch-TVAdvertisement $Handle $false 'campus' | Out-Null

        Wait-Agent $script:TVClickBufferMs
        Click-Relative $Handle 0.720 0.125 'Kampus crna zona ispod bustera - zatvori detalj'
        Wait-Agent $script:TVNavigationBufferMs
        Wait-CampusFlowState $Handle @('campus_maintenance') 25 | Out-Null
    }

    throw 'Kampus sigurnosni limit od 12 objekata je dostignut.'
}

function Invoke-BlueStacksAppCommand {
    param([ValidateSet('launchApp')][string]$Command)

    if (-not (Test-Path -LiteralPath $script:BlueStacksExe)) {
        throw "BlueStacks HD-Player nije pronadjen: $script:BlueStacksExe"
    }
    if ($script:DryRun) {
        Add-Log "DRY RUN: BlueStacks $Command za $script:TopElevenPackage"
        return
    }

    $arguments = @(
        '--instance', $script:BlueStacksInstance,
        '--cmd', $Command,
        '--package', $script:TopElevenPackage
    )
    # Kada je instanca ugasena ovaj proces postaje sam App Player i ne smije se
    # cekati niti ubiti kao kratkotrajni CLI helper.
    Start-Process -FilePath $script:BlueStacksExe -ArgumentList $arguments | Out-Null
}

function Stop-ExactBlueStacksInstanceForRecovery {
    param([IntPtr]$Handle)

    if ($script:DryRun) {
        Add-Log 'DRY RUN: gasenje tacne BlueStacks instance (force-stop fallback).'
        return
    }
    [uint32]$windowProcessId = 0
    [Win32Agent]::GetWindowThreadProcessId($Handle, [ref]$windowProcessId) | Out-Null
    $player = if ($windowProcessId -gt 0) {
        Get-Process -Id ([int]$windowProcessId) -ErrorAction SilentlyContinue
    }
    else { $null }
    if ($null -eq $player) {
        throw 'Nije pronadjen HD-Player proces koji pripada aktivnom BlueStacks prozoru.'
    }

    $playerId = $player.Id
    Add-Log "Gasim samo BlueStacks instancu PID $playerId; druge instance se ne diraju."
    try { $player.CloseMainWindow() | Out-Null } catch { }
    $graceDeadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $graceDeadline) {
        Test-Cancelled
        if ($null -eq (Get-Process -Id $playerId -ErrorAction SilentlyContinue)) { return }
        Wait-Agent 200
    }

    Add-Log "BlueStacks PID $playerId se nije ugasio uredno; primjenjujem force quit na tacno taj proces."
    Stop-Process -Id $playerId -Force -ErrorAction Stop
    Wait-ForCondition 'potpuno gasenje BlueStacks instance' 15 {
        return $null -eq (Get-Process -Id $playerId -ErrorAction SilentlyContinue)
    } | Out-Null
}

function Restart-TopElevenForStageRetry {
    param([string]$StageName)

    Add-Log "Recovery za fazu ${StageName}: radim potpuni force-stop paketa eu.nordeus.topeleven.android kroz restart tacne BlueStacks instance."
    Stop-VisionAgent
    Stop-XDetector
    $script:VisionCacheByState.Clear()
    $script:ForegroundStateCheckedAt = $null
    $script:ForegroundStateCache = $null
    $script:VisionUnavailableUntil = [datetime]::MinValue
    $script:AiTopElevenReturned = $false
    $script:AiAdVisible = $false
    $script:DetectedAdCloseX = $null
    $script:DetectedAdCloseY = $null
    $script:DetectedAdCloseKind = $null
    $script:DetectedPlayDestinationCloseX = $null
    $script:DetectedPlayDestinationCloseY = $null
    $script:DetectedFreeButtonX = $null
    $script:DetectedFreeButtonY = $null
    $script:FreeButtonStableCount = 0
    $script:FreeButtonStableSince = $null
    $script:LastGooglePlayClickAt = $null
    $script:LastHandledGooglePlayEvent = $null
    $script:LastGooglePlayBackAt = $null
    $script:GooglePlayRestoreKey = $null
    $script:GooglePlayBackAttemptCount = 0
    $script:ConnectionPopupLastCheckAt = [datetime]::MinValue
    $script:ConnectionPopupRecoveryActive = $false
    $script:PlayDestinationCheckedAt = $null
    $script:PlayDestinationCache = $false

    $oldHandle = Get-BlueStacksWindow -RequireConfiguredInstance
    if ($oldHandle -ne [IntPtr]::Zero) {
        Stop-ExactBlueStacksInstanceForRecovery $oldHandle
    }
    else {
        $unverifiedHandle = Get-BlueStacksWindow
        if ($unverifiedHandle -ne [IntPtr]::Zero) {
            throw "BlueStacks prozor postoji, ali nije potvrden kao instanca $script:BlueStacksInstance; recovery ga sigurnosno nece ugasiti niti preko njega pokrenuti novu instancu."
        }
        Add-Log 'BlueStacks prozor je vec zatvoren; prelazim direktno na ponovno pokretanje.'
    }
    Wait-Agent 2500
    Test-Cancelled

    $launchedAt = Get-Date
    if (Test-Path -LiteralPath $script:TopElevenShortcut) {
        Add-Log 'Ponovo pokrecem Top Eleven preko njegove BlueStacks precice.'
        if (-not $script:DryRun) {
            Start-Process -FilePath $script:TopElevenShortcut | Out-Null
        }
    }
    else {
        Add-Log 'Ponovo pokrecem Top Eleven preko BlueStacks LaunchApp naredbe.'
        Invoke-BlueStacksAppCommand 'launchApp'
    }

    $handle = [IntPtr]::Zero
    Wait-ForCondition 'BlueStacks prozor nakon force-stop recoveryja' 30 {
        $script:RecoveryWindowHandle = Get-BlueStacksWindow -RequireConfiguredInstance
        return $script:RecoveryWindowHandle -ne [IntPtr]::Zero
    } | Out-Null
    $handle = [IntPtr]$script:RecoveryWindowHandle
    [Win32Agent]::SetForegroundWindow($handle) | Out-Null
    if ($script:VisionEnabled) { Start-VisionAgent | Out-Null }

    $deadline = (Get-Date).AddSeconds($script:StageRecoveryLaunchTimeoutSeconds)
    $nextAiCheck = (Get-Date).AddSeconds(8)
    $nextPopupCheck = (Get-Date).AddSeconds(12)
    $stableHomeFrames = 0
    $stableAiHomeFrames = 0
    while ((Get-Date) -lt $deadline) {
        Test-Cancelled
        $activityReady = Test-TopElevenReturnedAfterAd $handle $launchedAt
        $visualHomeReady = (Test-GameHomeLoaded $handle) -and (Test-ResourcePlusReady $handle)
        if ($activityReady -and $visualHomeReady) {
            $stableHomeFrames++
            if ($stableHomeFrames -ge 2) {
                Add-Log 'Top Eleven je ponovo ucitan; Android aktivnost i dva stabilna pocetna framea su potvrdeni.'
                Wait-Agent 1000
                return $handle
            }
        }
        else {
            $stableHomeFrames = 0
        }
        if ($activityReady -and -not $visualHomeReady -and
            $script:VisionEnabled -and (Get-Date) -ge $nextPopupCheck) {
            $popupHandled = Try-RecoverConnectionInterruptedPopup $handle
            $stableHomeFrames = 0
            $stableAiHomeFrames = 0
            $nextPopupCheck = (Get-Date).AddSeconds(15)
            $nextAiCheck = (Get-Date).AddSeconds(10)
            if ($popupHandled) { continue }
        }
        if ($script:VisionEnabled -and (Get-Date) -ge $nextAiCheck) {
            $recoveryState = "stage_recovery_top_eleven_ai_only_$((Get-Date).Ticks)"
            Test-AiOnlyAdControlReady $handle $recoveryState -ForceRefresh | Out-Null
            if ($activityReady -and $script:AiTopElevenReturned) {
                $stableAiHomeFrames++
                Add-Log "AI potvrda ponovo ucitanog Top Elevena: $stableAiHomeFrames/2."
                if ($stableAiHomeFrames -ge 2) {
                    return $handle
                }
            }
            else {
                $stableAiHomeFrames = 0
            }
            $nextAiCheck = (Get-Date).AddSeconds(10)
        }
        Wait-Agent 500
    }
    throw "Top Eleven se nije ponovo ucitao tokom $script:StageRecoveryLaunchTimeoutSeconds sekundi."
}

function Invoke-VerifiedStageRecovery {
    param([string]$StageName)

    $recoveryError = $null
    for ($recoveryAttempt = 1; $recoveryAttempt -le $script:StageRetryAttempts; $recoveryAttempt++) {
        try {
            return [IntPtr](Restart-TopElevenForStageRetry $StageName)
        }
        catch [System.OperationCanceledException] { throw }
        catch {
            $recoveryError = $_.Exception
            Add-Log "Recovery za fazu $StageName nije uspio ($recoveryAttempt/$script:StageRetryAttempts): $($recoveryError.Message)"
            if ($recoveryAttempt -lt $script:StageRetryAttempts) {
                Set-Status "Recovery za $StageName jos nije spreman - ponavljam potpuno pokretanje..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                Wait-Agent 2000
            }
        }
    }
    throw $recoveryError
}

function Invoke-StageWithRecovery {
    param(
        [string]$Name,
        [IntPtr]$Handle,
        [scriptblock]$Action
    )

    $lastError = $null
    $attemptHandle = $Handle
    if ($script:StagePreflightRecoveryRequired) {
        Add-Log "Faza $Name zahtijeva potvrden pocetni ekran prije prvog klika."
        try {
            $attemptHandle = Invoke-VerifiedStageRecovery "$Name - obavezna priprema"
            $script:StagePreflightRecoveryRequired = $false
        }
        catch [System.OperationCanceledException] { throw }
        catch {
            $lastError = $_.Exception
            Add-Log "Faza $Name nije pokrenuta jer verificirani pocetni ekran nije vracen: $($lastError.Message)"
            return [PSCustomObject]@{ Success = $false; Handle = [IntPtr]::Zero; Error = $lastError; Attempts = 0 }
        }
    }
    for ($attempt = 1; $attempt -le $script:StageRetryAttempts; $attempt++) {
        Test-Cancelled
        Add-Log "===== FAZA: $Name - POKUSAJ $attempt/$script:StageRetryAttempts ====="
        try {
            $attemptHandle = Get-BlueStacksWindow -RequireConfiguredInstance
            if ($attemptHandle -eq [IntPtr]::Zero) { throw 'BlueStacks prozor nije pronadjen.' }
            $null = & $Action $attemptHandle
            Add-Log "===== FAZA ZAVRSENA: $Name ====="
            return [PSCustomObject]@{ Success = $true; Handle = $attemptHandle; Error = $null; Attempts = $attempt }
        }
        catch [System.OperationCanceledException] {
            throw
        }
        catch {
            $lastError = $_.Exception
            Add-Log "Faza $Name nije uspjela u pokusaju $attempt/$script:StageRetryAttempts: $($lastError.Message)"
            if ($attempt -lt $script:StageRetryAttempts) {
                Set-Status "Faza $Name nije uspjela - force-stop i ponovni pokusaj..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                try {
                    $attemptHandle = Invoke-VerifiedStageRecovery $Name
                }
                catch [System.OperationCanceledException] { throw }
                catch {
                    $lastError = $_.Exception
                    Add-Log "Faza $Name se nece pokretati na loading ili popup ekranu; sva tri recovery pokusaja su iscrpljena."
                    return [PSCustomObject]@{ Success = $false; Handle = [IntPtr]::Zero; Error = $lastError; Attempts = $attempt }
                }
            }
        }
    }
    return [PSCustomObject]@{ Success = $false; Handle = $attemptHandle; Error = $lastError; Attempts = $script:StageRetryAttempts }
}

function Invoke-CombinedStage {
    param(
        [string]$Name,
        [IntPtr]$Handle,
        [scriptblock]$Action
    )

    Add-Log "===== POCETAK FAZE: $Name ====="
    $result = Invoke-StageWithRecovery -Name $Name -Handle $Handle -Action $Action
    if ($result.Success) { return $true }
    $message = if ($null -ne $result.Error) { $result.Error.Message } else { 'nepoznata greska' }
    $script:HadStageFailures = $true
    Add-Log "Faza $Name nije uspjela ni nakon $script:StageRetryAttempts pokusaja: $message"
    Set-Status "Faza $Name nije uspjela nakon tri pokusaja - nastavljam na sljedecu fazu..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
    try {
        # Posljednji neuspjeli pokusaj moze ostaviti proizvoljan ekran. Ocisti
        # stanje prije sljedece kombinovane faze, ali ne pokreci opet ovu fazu.
        Invoke-VerifiedStageRecovery "$Name - priprema sljedece faze" | Out-Null
        $script:StagePreflightRecoveryRequired = $false
    }
    catch [System.OperationCanceledException] { throw }
    catch {
        $script:StagePreflightRecoveryRequired = $true
        Add-Log "Zavrsni recovery prije sljedece faze nije uspio nakon tri pokusaja: $($_.Exception.Message)"
    }
    Wait-Agent 2000
    return $false
}

if ($SelfTest) {
    "BlueStacks executable: $(Test-Path -LiteralPath $script:BlueStacksExe)"
    "Configured instance: $script:BlueStacksInstance"
    "Configured display name: $(Get-BlueStacksInstanceDisplayName)"
    "Top Eleven shortcut: $(Test-Path -LiteralPath $script:TopElevenShortcut)"
    "Visible configured BlueStacks window: $((Get-BlueStacksWindow -RequireConfiguredInstance) -ne [IntPtr]::Zero)"
    "Config loaded: $($null -ne $script:Config)"
    "Dry run: $script:DryRun"
    "Vision agent script: $(Test-Path -LiteralPath $script:VisionAgentScript)"
    "Vision enabled: $script:VisionEnabled"
    exit 0
}

function Start-Automation {
    if ($script:Running) { return }
    if ($script:Mode -eq 'OdmoriEkipu' -and $null -ne $teamRestStartCombo -and $teamRestStartCombo.SelectedIndex -ge 0) {
        $script:TeamRestStartKey = [string]$script:TeamRestQueue[$teamRestStartCombo.SelectedIndex].Key
    }
    $script:Running = $true
    $script:Cancelled = $false
    $startButton.Enabled = $false
    $stopButton.Enabled = $true
    if ($null -ne $teamRestStartCombo) {
        $teamRestStartCombo.Enabled = $false
    }

    try {
        Set-Status 'Koristim vec otvoreni Top Eleven i odmah pokrecem glavni dio...'
        $handle = Get-BlueStacksWindow -RequireConfiguredInstance
        if ($handle -eq [IntPtr]::Zero) {
            throw 'Otvoreni BlueStacks prozor nije pronadjen.'
        }
        [Win32Agent]::SetForegroundWindow($handle) | Out-Null
        if ($script:VisionEnabled) { Start-VisionAgent | Out-Null }
        Wait-Agent $script:ShortTransitionBufferMs

        if ($script:Calibration) {
            $viewport = Get-GameViewportRectangle $handle
            Add-Log ("Game viewport: Left={0}, Top={1}, Right={2}, Bottom={3}" -f $viewport.Left, $viewport.Top, $viewport.Right, $viewport.Bottom)
            Click-GameRelative $handle 0.014 0.068 'kalibracija - bocni meni'
            Click-GameRelative $handle 0.087 0.189 'kalibracija - Trening'
            Click-GameRelative $handle 0.124 0.914 'kalibracija - Fizio centar'
            Click-GameRelative $handle 0.778 0.880 'kalibracija - BESPLATNO'
            Set-Status 'Kalibracija zavrsena bez klikanja.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
            return
        }

        $runGreenStage = $script:Mode -eq 'Zeleni'
        if ($script:Mode -eq 'Sve') {
            $combinedStages = @(
                [PSCustomObject]@{ Key = 'Mourinho';   Name = 'Mourinho';      Action = { param($stageHandle) Run-MourinhoAutomation $stageHandle } },
                [PSCustomObject]@{ Key = 'TV';         Name = 'Top Eleven TV'; Action = { param($stageHandle) Run-TVAutomation $stageHandle } },
                [PSCustomObject]@{ Key = 'PutSaveza'; Name = 'Put saveza';    Action = { param($stageHandle) Run-PutSavezaAutomation $stageHandle } },
                [PSCustomObject]@{ Key = 'Kampus';    Name = 'Kampus';        Action = { param($stageHandle) Run-CampusAutomation $stageHandle } },
                [PSCustomObject]@{ Key = 'Zeleni';    Name = 'Uzmi 25 zelenih'; Action = $null }
            )
            $stageKeys = @($combinedStages | ForEach-Object { [string]$_.Key })
            $startIndex = [Array]::IndexOf($stageKeys, [string]$script:CombinedStartStage)
            if ($startIndex -lt 0) { $startIndex = 0 }
            Add-Log "Pokreni sve pocinje od faze: $($combinedStages[$startIndex].Name)."
            for ($stageIndex = $startIndex; $stageIndex -lt $combinedStages.Count; $stageIndex++) {
                $stage = $combinedStages[$stageIndex]
                if ($stage.Key -eq 'Zeleni') {
                    $runGreenStage = $true
                    break
                }
                Invoke-CombinedStage $stage.Name $handle $stage.Action | Out-Null
                Test-Cancelled
                $freshHandle = Get-BlueStacksWindow -RequireConfiguredInstance
                if ($freshHandle -ne [IntPtr]::Zero) { $handle = $freshHandle }
            }
        }
        elseif ($script:Mode -eq 'Mourinho') {
            $stageResult = Invoke-StageWithRecovery 'Mourinho' $handle { param($stageHandle) Run-MourinhoAutomation $stageHandle }
            if (-not $stageResult.Success) { throw "Mourinho nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }
        elseif ($script:Mode -eq 'Kampus') {
            $stageResult = Invoke-StageWithRecovery 'Kampus' $handle { param($stageHandle) Run-CampusAutomation $stageHandle }
            if (-not $stageResult.Success) { throw "Kampus nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }
        elseif ($script:Mode -eq 'PutSaveza') {
            $stageResult = Invoke-StageWithRecovery 'Put saveza' $handle { param($stageHandle) Run-PutSavezaAutomation $stageHandle }
            if (-not $stageResult.Success) { throw "Put saveza nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }
        elseif ($script:Mode -eq 'TreningIgraca') {
            $stageResult = Invoke-StageWithRecovery 'Trening igraca' $handle { param($stageHandle) Run-TrainingPlayerAutomation $stageHandle }
            if (-not $stageResult.Success) { throw "Trening igraca nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }
        elseif ($script:Mode -eq 'TV') {
            $stageResult = Invoke-StageWithRecovery 'Top Eleven TV' $handle { param($stageHandle) Run-TVAutomation $stageHandle }
            if (-not $stageResult.Success) { throw "Top Eleven TV nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }
        elseif ($script:Mode -eq 'OdmoriEkipu') {
            $stageResult = Invoke-StageWithRecovery 'Odmori igrace' $handle {
                param($stageHandle)
                $handle = $stageHandle
                Open-TeamRest $handle
                Run-TeamRestManualQueue $handle $script:TeamRestStartKey
            }
            if (-not $stageResult.Success) { throw "Odmor igraca nije uspio nakon $script:StageRetryAttempts pokusaja: $($stageResult.Error.Message)" }
            return
        }

        if (-not $runGreenStage) { return }
        $greenResult = Invoke-StageWithRecovery 'Uzmi 25 zelenih' $handle {
            param($stageHandle)
            $handle = $stageHandle
            Open-Store $handle

            # === GLAVNA PETLJA - ponavlja dok dugme BESPLATNO ne postane sivo ===
            $freeButtonDisabled = $false
            $totalAdsWatched = 0

        while (-not $freeButtonDisabled -and -not $script:Cancelled) {
            Set-Status 'Cekam da dugme BESPLATNO postane dostupno...'
            Wait-ForCondition 'aktivno dugme BESPLATNO' 90 {
                Test-FreeButtonReady $handle
            } | Out-Null

            [Win32Agent]::SetForegroundWindow($handle) | Out-Null
            Set-Status ("BESPLATNO je spremno - kliknem automatski. (reklama #{0})" -f ($totalAdsWatched + 1)) ([System.Drawing.Color]::FromArgb(120, 240, 150))

            if ($script:Mode -eq 'OdmoriEkipu') {
                Click-GameRelative $handle 0.778 0.880 'BESPLATNO - odmor GK'
            }
            else {
                Click-Relative $handle 0.890 0.245 'BESPLATNO'
            }
            $adStartedAt = Get-Date

            Set-Status ("Reklama je pokrenuta. Prva AI provjera dugmadi pocinje za {0:N1} sekundi..." -f $script:VisionAiProbeIntervalSeconds)
            $adCloseDeadline = (Get-Date).AddMinutes(5)
            $xDetectionStartsAt = (Get-Date).AddSeconds($script:XDetectionDelaySeconds)
            $aiOnlyFallbackStartsAt = $adStartedAt.AddSeconds($script:VisionAiOnlyFallbackAfterSeconds)
            # Nema posebnog AI probea nakon 5 sekundi; prvi je puni redovni interval.
            $nextAiProbeAt = $adStartedAt.AddSeconds($script:VisionAiProbeIntervalSeconds)
            $aiOnlyExpectedState = "ad_control_ai_only_$($adStartedAt.Ticks)"
            $aiOnlyFallbackLogged = $false
            $googlePlayBadgeClicked = $false
            $detectedGooglePlayAttemptCount = 0
            $nextDetectedGooglePlayAttemptAt = $adStartedAt
            $googlePlayReminderAt = (Get-Date).AddSeconds($script:AdWaitSeconds + 15)
            $googlePlayReminderShown = $false
            $xDetectionStarted = $false
            $adCloseReady = $false
            $adAlreadyExited = $false
            $adObserved = $false
            $nextAdWakeTapAt = $adStartedAt.AddSeconds($script:AdWakeTapAfterSeconds)
            $adWakeBurstUntil = $null
            $adWakeTapCount = 0

            while ((Get-Date) -lt $adCloseDeadline) {
                Test-Cancelled
                if (Restore-AdFromGooglePlay $handle $adStartedAt) {
                    $googlePlayBadgeClicked = $true
                    $adObserved = $true
                    Start-Sleep -Milliseconds 50
                    continue
                }
                if ((Get-Date) -ge $nextAdWakeTapAt -and $adWakeTapCount -lt $script:AdWakeTapMaximum) {
                    $adWakeTapCount++
                    Set-Status 'Reklama dugo traje - dodirujem ekran da ponovo prikazem kratku kontrolu...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    Click-Relative $handle 0.500 0.620 'reklama - probudi skrivenu kontrolu'
                    $adWakeBurstUntil = (Get-Date).AddSeconds($script:AdWakeBurstSeconds)
                    $nextAdWakeTapAt = (Get-Date).AddSeconds($script:AdWakeTapIntervalSeconds)
                    $script:VisionCacheByState.Remove($aiOnlyExpectedState)
                    $nextAiProbeAt = Get-Date
                    Add-Log 'Wake provjera: AI provjera krece odmah.'
                }
                $wakeBurstActive = $null -ne $adWakeBurstUntil -and (Get-Date) -lt $adWakeBurstUntil
                $aiOnlyFallbackActive = $false
                if ($aiOnlyFallbackActive) {
                    if (-not $aiOnlyFallbackLogged) {
                        $aiOnlyFallbackLogged = $true
                        Set-Status "Reklama je i dalje otvorena nakon $script:VisionAiOnlyFallbackAfterSeconds sekundi - prelazim na AI-only detekciju..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    }
                }
                if ($script:VisionEnabled -and (Get-Date) -ge $nextAiProbeAt) {
                    $nextAiProbeAt = (Get-Date).AddSeconds($script:VisionAiProbeIntervalSeconds)
                    Add-Log 'AI periodicna provjera kontrole...'
                    $aiControlReady = Test-AiOnlyAdControlReady $handle $aiOnlyExpectedState
                    if ($script:AiAdVisible) { $adObserved = $true }
                    if ($script:AiTopElevenReturned -and $adObserved) {
                        $adAlreadyExited = $true
                        Add-Log 'AI je potvrdio da je reklama vec zatvorena; ne klikcem stare koordinate.'
                        break
                    }
                    if ($script:AiTopElevenReturned -and -not $adObserved) {
                        Add-Log 'AI jos vidi pocetni Top Eleven ekran, ali reklama nije bila opazena; cekam ucitavanje reklame.'
                    }
                    if ($aiControlReady) {
                        if ($script:DetectedAdCloseKind -eq 'skip') {
                            Click-Relative $handle $script:DetectedAdCloseX $script:DetectedAdCloseY '>> - AI-only nastavi reklamu'
                            Wait-Agent $script:TransitionBufferMs
                            $aiOnlyExpectedState = "ad_control_ai_only_$((Get-Date).Ticks)"
                            continue
                        }
                        if ($script:DetectedAdCloseKind -eq 'google_play') {
                            $script:LastGooglePlayClickAt = Get-Date
                            Click-Relative $handle $script:DetectedAdCloseX $script:DetectedAdCloseY 'Google Play dugme - AI-only'
                            Wait-Agent 2000
                            Restore-AdFromGooglePlay $handle $adStartedAt | Out-Null
                            $aiOnlyExpectedState = "ad_control_ai_only_$((Get-Date).Ticks)"
                            continue
                        }
                        $adCloseReady = $true
                        break
                    }
                }
                if ($aiOnlyFallbackActive) {
                    Start-Sleep -Milliseconds 50
                    continue
                }
                if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt -and (Test-YellowAdControlReady $handle)) {
                    if ($script:DetectedYellowControlKind -eq 'google_play') {
                        # A real close X always wins over a yellow Play candidate.
                        if (Test-AdCloseReady $handle) {
                            if ($script:DetectedAdCloseKind -eq 'skip') {
                                Click-Relative $handle $script:DetectedAdCloseX $script:DetectedAdCloseY '>> - nastavi reklamu'
                                Wait-Agent $script:TransitionBufferMs
                                $script:XDetectorStableCount = 0
                                $script:XDetectorStableSince = $null
                                continue
                            }
                            $adCloseReady = $true
                            break
                        }
                        if (-not $googlePlayBadgeClicked -and
                            $detectedGooglePlayAttemptCount -lt 3 -and
                            (Get-Date) -ge $nextDetectedGooglePlayAttemptAt) {
                            $detectedGooglePlayAttemptCount++
                            $nextDetectedGooglePlayAttemptAt = (Get-Date).AddSeconds(4)
                            Set-Status 'Google Play dugme je pronadjeno - otvaram Store...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                            if (Invoke-DetectedGooglePlayControl $handle $adStartedAt 'Google Play dugme') {
                                $googlePlayBadgeClicked = $true
                            }
                            continue
                        }
                    }
                    else {
                        $script:DetectedAdCloseX = $script:DetectedYellowControlX
                        $script:DetectedAdCloseY = $script:DetectedYellowControlY
                        $script:DetectedAdCloseKind = 'close'
                        $adCloseReady = $true
                        Set-Status 'Zuti X je pronadjen.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
                        break
                    }
                }
                if (-not $script:AdControlsAiOnly -and (Get-Date) -ge $xDetectionStartsAt) {
                    if (-not $xDetectionStarted) {
                        $xDetectionStarted = $true
                        Set-Status 'Pokrecem brzu detekciju X-a...'
                    }
                    if (Test-AdCloseReady $handle) {
                        if ($script:DetectedAdCloseKind -eq 'skip') {
                            Set-Status 'Dugme >> je spremno - nastavljam reklamu...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                            Click-Relative $handle $script:DetectedAdCloseX $script:DetectedAdCloseY '>> - nastavi reklamu'
                            Wait-Agent $script:TransitionBufferMs
                            $script:XDetectorStableCount = 0
                            $script:XDetectorStableSince = $null
                            continue
                        }
                        $adCloseReady = $true
                        break
                    }
                }

                if (-not $googlePlayReminderShown -and (Get-Date) -ge $googlePlayReminderAt) {
                    $googlePlayReminderShown = $true
                    Set-Status 'X jos nije dostupan; nastavljam cekati i automatski nadgledati Google Play Store.' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                }

                Start-Sleep -Milliseconds 50
            }

            if (-not $adCloseReady -and -not $adAlreadyExited) {
                throw 'X nije prepoznat u roku od 5 minuta.'
            }

            $adClosed = $adAlreadyExited
            if (-not $adAlreadyExited) {
                [Win32Agent]::SetForegroundWindow($handle) | Out-Null
                Set-Status 'X je dostupan - zatvaram reklamu automatski.' ([System.Drawing.Color]::FromArgb(120, 240, 150))

                while ((Get-Date) -lt $adCloseDeadline -and -not $adClosed) {
                    Test-Cancelled
                    $preClickState = Confirm-AiAdCloseImmediatelyBeforeClick $handle 'Reklama'
                    if ($preClickState -eq 'returned') {
                        $adClosed = $true
                        break
                    }
                    if ($preClickState -ne 'close') {
                        Set-Status 'Reklama je jos pod nadzorom - cekam novu svjezu AI potvrdu X-a ili povratka...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                        Wait-Agent 1000
                        continue
                    }
                    if ($null -eq $script:DetectedAdCloseX -or $null -eq $script:DetectedAdCloseY) {
                        throw 'AI nije vratio koordinate X-a.'
                    }
                    $closeX = [double]$script:DetectedAdCloseX
                    $closeY = [double]$script:DetectedAdCloseY
                    Click-Relative $handle $closeX $closeY 'X (zatvori reklamu)'
                    Wait-Agent $script:TransitionBufferMs
                    if (Restore-AdFromGooglePlay $handle $adStartedAt) {
                        $xAfterStore = Wait-ForAdXAfterGooglePlayReturn $handle $adCloseDeadline $adStartedAt 'reklamu'
                        if ($script:AiTopElevenReturned) {
                            $adClosed = $true
                            break
                        }
                        if (-not $xAfterStore) {
                            throw 'Nakon povratka iz Google Play Storea X nije pronadjen.'
                        }
                        continue
                    }
                    $exitState = Wait-ForAdExitOrControl $handle 10 $adStartedAt
                    if ($exitState -eq 'exited') {
                        $adClosed = $true
                        Add-Log 'Top Eleven je potvrden Android aktivnoscu ili AI analizom nakon reklame.'
                        break
                    }
                    if ($exitState -eq 'control') {
                        Add-Log 'Reklama je jos otvorena; pronadjena je nova aktivna kontrola.'
                        continue
                    }
                    Add-Log 'Povratak jos nije potvrden; nastavljam automatski nadzor umjesto prekida.'
                    Wait-Agent 1000
                }
            }

            if ($adClosed) {
                $totalAdsWatched++
                Add-Log "Reklama #$totalAdsWatched uspjesno zatvorena."
                Wait-Agent $script:ShortTransitionBufferMs

                # Provjeri je li dugme BESPLATNO postalo sivo (nedostupno)
                # Nakon zatvaranja reklame, vrati se na ekran prodavnice
                Set-Status 'Provjeravam je li dugme BESPLATNO jos uvijek dostupno...'
                
                # Ponekad treba malo vremena da se prodavnica osvjezi
                Wait-Agent $script:ShortTransitionBufferMs
                
                if ($script:Mode -eq 'OdmoriEkipu') {
                    Click-GameRelative $handle 0.976 0.256 'GK plus - sljedeci odmor'
                    Wait-Agent $script:TransitionBufferMs
                }
                else {
                    # Ako prodavnica nije vidljiva, pokusaj je ponovo otvoriti
                    if (-not (Test-StoreLoaded $handle)) {
                        Add-Log 'Prodavnica nije vidljiva, pokusavam ponovo otvoriti...'
                        Open-Store $handle
                    }
                }

                # Provjeri je li dugme BESPLATNO jos uvijek aktivno
                $stillAvailable = Test-FreeButtonReady $handle
                
                if (-not $stillAvailable) {
                    $freeButtonDisabled = $true
                    [System.Media.SystemSounds]::Exclamation.Play()
                    Set-Status "Sve reklame su pogledane! Ukupno: $totalAdsWatched reklama." ([System.Drawing.Color]::FromArgb(120, 240, 150))
                    if (-not $script:ExitAfterRun) {
                        [System.Windows.Forms.MessageBox]::Show(
                            $form,
                            "Sve dostupne reklame su pogledane!`r`n`r`nUkupno pogledanih reklama: $totalAdsWatched",
                            'Top Eleven Agent - zavrseno',
                            [System.Windows.Forms.MessageBoxButtons]::OK,
                            [System.Windows.Forms.MessageBoxIcon]::Information
                        ) | Out-Null
                    }
                }
                else {
                    Set-Status "Reklama #$totalAdsWatched zatvorena. Cekam sljedecu..." ([System.Drawing.Color]::FromArgb(220, 235, 255))
                    Wait-Agent $script:TransitionBufferMs
                    # Nastavi petlju za sljedecu reklamu
                }
            }
            else {
                throw 'Reklama nije automatski zavrsena niti je povratak u Top Eleven potvrdjen u roku od 5 minuta.'
            }
        }

            if ($freeButtonDisabled) {
                Set-Status "Sve reklame pogledane! ($totalAdsWatched reklama)" ([System.Drawing.Color]::FromArgb(120, 240, 150))
            }
        }
        if (-not $greenResult.Success) {
            throw "Uzmi 25 zelenih nije uspio nakon $script:StageRetryAttempts pokusaja: $($greenResult.Error.Message)"
        }
    }
    catch [System.OperationCanceledException] {
        Set-Status 'Automatizacija je zaustavljena.' ([System.Drawing.Color]::FromArgb(255, 210, 100))
    }
    catch {
        $script:RunFailed = $true
        Set-Status "Greska: $($_.Exception.Message)" ([System.Drawing.Color]::FromArgb(255, 120, 120))
        if (-not $script:ExitAfterRun) {
            [System.Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, 'Top Eleven Agent - greska', 'OK', 'Error') | Out-Null
        }
    }
    finally {
        Stop-VisionAgent
        Stop-XDetector
        $script:Running = $false
        $startButton.Enabled = $true
        $stopButton.Enabled = $false
        if ($null -ne $teamRestStartCombo) {
            $teamRestStartCombo.Enabled = $true
        }
    }
}

$isTeamRestMode = $script:Mode -eq 'OdmoriEkipu'
$formHeight = if ($isTeamRestMode) { 405 } else { 335 }
$buttonTop = if ($isTeamRestMode) { 153 } else { 98 }
$logTop = if ($isTeamRestMode) { 208 } else { 153 }
$logHeight = if ($isTeamRestMode) { 145 } else { 130 }
$teamRestStartCombo = $null

$form = New-Object System.Windows.Forms.Form
$form.Text = switch ($script:Mode) {
    'OdmoriEkipu' { 'Top Eleven Odmor igraca AI Agent' }
    'TV' { 'Top Eleven TV AI Agent' }
    'Mourinho' { 'Top Eleven Mourinho AI Agent' }
    'Kampus' { 'Top Eleven Kampus AI Agent' }
    'PutSaveza' { 'Top Eleven Put saveza AI Agent' }
    'TreningIgraca' { 'Top Eleven Trening igraca AI Agent' }
    'Sve' { 'Top Eleven Kompletni AI Agent' }
    default { 'Top Eleven AI Vision Agent' }
}
$form.Size = New-Object System.Drawing.Size(470, $formHeight)
$form.MinimumSize = New-Object System.Drawing.Size(470, $formHeight)
$form.StartPosition = 'Manual'
$workingArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(15, ($workingArea.Bottom - $form.Height - 15))
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(24, 29, 45)
$form.ForeColor = [System.Drawing.Color]::White
if ($script:AutoStart -and $script:ExitAfterRun) {
    # Centralni manager prikazuje status i log; child zadrzava WinForms message
    # loop zbog postojece automatizacije, ali ne otvara drugi prozor preko igre.
    $form.ShowInTaskbar = $false
    $form.TopMost = $false
    $form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
}

$title = New-Object System.Windows.Forms.Label
$title.Text = switch ($script:Mode) {
    'OdmoriEkipu' { 'TOP ELEVEN ODMOR IGRACA' }
    'TV' { 'TOP ELEVEN TV AI AGENT' }
    'Mourinho' { 'TOP ELEVEN MOURINHO AI AGENT' }
    'Kampus' { 'TOP ELEVEN KAMPUS AI AGENT' }
    'PutSaveza' { 'TOP ELEVEN PUT SAVEZA AI AGENT' }
    'TreningIgraca' { 'TOP ELEVEN TRENING IGRACA' }
    'Sve' { 'TOP ELEVEN KOMPLETNI AI AGENT' }
    default { 'TOP ELEVEN AI VISION AGENT' }
}
$title.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 16)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(18, 15)
$title.ForeColor = [System.Drawing.Color]::FromArgb(88, 220, 105)
$form.Controls.Add($title)

$status = New-Object System.Windows.Forms.Label
$status.Text = 'Spremno za pokretanje.'
$status.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$status.Location = New-Object System.Drawing.Point(20, 53)
$status.Size = New-Object System.Drawing.Size(420, 42)
$form.Controls.Add($status)

if ($isTeamRestMode) {
    $teamRestStartLabel = New-Object System.Windows.Forms.Label
    $teamRestStartLabel.Text = 'Pocni od pozicije:'
    $teamRestStartLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $teamRestStartLabel.Location = New-Object System.Drawing.Point(20, 98)
    $teamRestStartLabel.Size = New-Object System.Drawing.Size(140, 22)
    $form.Controls.Add($teamRestStartLabel)

    $teamRestStartCombo = New-Object System.Windows.Forms.ComboBox
    $teamRestStartCombo.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
    $teamRestStartCombo.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $teamRestStartCombo.Location = New-Object System.Drawing.Point(160, 95)
    $teamRestStartCombo.Size = New-Object System.Drawing.Size(283, 28)
    foreach ($player in $script:TeamRestQueue) {
        [void]$teamRestStartCombo.Items.Add([string]$player.Display)
    }
    $selectedStartIndex = 0
    for ($index = 0; $index -lt $script:TeamRestQueue.Count; $index++) {
        if ([string]$script:TeamRestQueue[$index].Key -eq $script:TeamRestStartKey) {
            $selectedStartIndex = $index
            break
        }
    }
    $teamRestStartCombo.SelectedIndex = $selectedStartIndex
    $form.Controls.Add($teamRestStartCombo)
}

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'POKRENI'
$startButton.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
$startButton.Location = New-Object System.Drawing.Point(20, $buttonTop)
$startButton.Size = New-Object System.Drawing.Size(205, 42)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(48, 180, 75)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = 'Flat'
$startButton.Add_Click({ Start-Automation })
$form.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'ZAUSTAVI'
$stopButton.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
$stopButton.Location = New-Object System.Drawing.Point(238, $buttonTop)
$stopButton.Size = New-Object System.Drawing.Size(205, 42)
$stopButton.BackColor = [System.Drawing.Color]::FromArgb(165, 55, 65)
$stopButton.ForeColor = [System.Drawing.Color]::White
$stopButton.FlatStyle = 'Flat'
$stopButton.Enabled = $false
$stopButton.Add_Click({
    $script:Cancelled = $true
    $stopButton.Enabled = $false
})
$form.Controls.Add($stopButton)

$log = New-Object System.Windows.Forms.TextBox
$log.Multiline = $true
$log.ReadOnly = $true
$log.ScrollBars = 'Vertical'
$log.Location = New-Object System.Drawing.Point(20, $logTop)
$log.Size = New-Object System.Drawing.Size(423, $logHeight)
$log.BackColor = [System.Drawing.Color]::FromArgb(14, 18, 29)
$log.ForeColor = [System.Drawing.Color]::FromArgb(210, 220, 235)
$log.Font = New-Object System.Drawing.Font('Consolas', 9)
$form.Controls.Add($log)

$form.Add_FormClosing({
    if ($script:Running) {
        $_.Cancel = $true
        $script:Cancelled = $true
    }
})

Add-Log 'Spremno. Pritisnite POKRENI.'
if ($script:AutoStart) {
    $form.Add_Shown({
        $form.BeginInvoke([System.Action]{
            Start-Automation
            if ($script:ExitAfterRun -and -not $form.IsDisposed) {
                $form.Close()
            }
        }) | Out-Null
    })
}
[void]$form.ShowDialog()
if ($script:ExitAfterRun) {
    if ($script:RunFailed) { exit 1 }
    if ($script:HadStageFailures) { exit 2 }
}
