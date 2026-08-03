param(
    [switch]$SelfTest,
    [ValidateSet('Zeleni', 'OdmoriEkipu')]
    [string]$Mode = 'Zeleni'
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
}
'@

[Win32Agent]::SetProcessDPIAware() | Out-Null

$script:BlueStacksExe = 'C:\Program Files\BlueStacks_nxt\HD-Player.exe'
$script:BlueStacksInstance = 'Pie64'
$script:WindowTitle = 'BlueStacks App Player'
$script:TopElevenShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Top Eleven - BlueStacks App Player 1.lnk'
$script:PythonExe = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$script:XDetectorScript = Join-Path $PSScriptRoot 'XDetector.py'
$script:BlueStacksPlayerLog = 'C:\ProgramData\BlueStacks_nxt\Logs\Player.log'
$script:ForegroundStateCache = $null
$script:ForegroundStateCheckedAt = $null
$script:LastHandledGooglePlayEvent = $null
$script:LastGooglePlayBackAt = $null
$script:Mode = $Mode
$script:Cancelled = $false
$script:Running = $false

function Add-Log {
    param([string]$Text)
    $stamp = Get-Date -Format 'HH:mm:ss'
    $log.AppendText("[$stamp] $Text`r`n")
    $log.SelectionStart = $log.TextLength
    $log.ScrollToCaret()
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

function Get-BlueStacksWindow {
    return [Win32Agent]::FindVisibleWindow($script:WindowTitle)
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
    throw "Isteklo je vrijeme čekanja: $Description"
}

function Get-WindowRectangle {
    param([IntPtr]$Handle)
    $rect = New-Object Win32Agent+RECT
    if (-not [Win32Agent]::GetWindowRect($Handle, [ref]$rect)) {
        throw 'Nije moguće očitati veličinu BlueStacks prozora.'
    }
    return $rect
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
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 30
    [Win32Agent]::SetCursorPos($screenX, $screenY) | Out-Null
    [Win32Agent]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Add-Log "Klik: $Name ($screenX, $screenY)"
}

function Send-Escape {
    param([IntPtr]$Handle)
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 30
    [Win32Agent]::keybd_event(0x1B, 0, 0, [UIntPtr]::Zero)
    [Win32Agent]::keybd_event(0x1B, 0, 0x0002, [UIntPtr]::Zero)
    Add-Log 'Pokušaj zatvaranja popupa: Back / Escape'
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
                if ($line -match 'hcallOnActivityDisplayedClbk\s*:\s*package\s*=\s*(?<Package>[^\s]+)') {
                    $eventTime = $null
                    if ($line.Length -ge 28) {
                        $parsedTime = [DateTimeOffset]::MinValue
                        if ([DateTimeOffset]::TryParse($line.Substring(0, 28), [ref]$parsedTime)) {
                            $eventTime = $parsedTime.LocalDateTime
                        }
                    }
                    $state = [PSCustomObject]@{
                        Package = [string]$Matches.Package
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

function Restore-AdFromGooglePlay {
    param(
        [IntPtr]$Handle,
        [datetime]$AdStartedAt
    )

    $state = Get-BlueStacksForegroundState
    if ($null -eq $state -or $state.Package -ne 'com.android.vending') {
        return $false
    }
    if ($null -ne $state.EventTime -and $state.EventTime -lt $AdStartedAt.AddSeconds(-2)) {
        return $false
    }

    # Jedan Back po konkretnom Play Store dogadjaju. Dok se zapisnik ne
    # osvjezi, ne smijemo poslati drugi Back.
    if ($script:LastHandledGooglePlayEvent -ne $state.Signature) {
        $script:LastHandledGooglePlayEvent = $state.Signature
        $script:LastGooglePlayBackAt = Get-Date
        Set-Status 'Otvoren je Google Play Store - vracam se jednim Back klikom...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
        Click-Relative $Handle 0.132 0.018 'BlueStacks Back - povratak iz Google Play Storea'
        Wait-Agent 900
        $script:ForegroundStateCheckedAt = $null
        $script:XDetectorStableCount = 0
        $script:XDetectorStableSince = $null
        $script:XDetectorLastX = $null
        $script:XDetectorLastY = $null
        Add-Log 'Back je pritisnut jednom; nastavljam cekati pravi X reklame.'
        return $true
    }
    if ($null -ne $script:LastGooglePlayBackAt -and
        ((Get-Date) - $script:LastGooglePlayBackAt).TotalSeconds -lt 2) {
        return $true
    }
    return $false
}

function Wait-ForAdXAfterGooglePlayReturn {
    param(
        [IntPtr]$Handle,
        [datetime]$Deadline,
        [datetime]$AdStartedAt,
        [string]$Label
    )

    Set-Status "Vracen sam iz Google Play Storea; nastavljam cekati pravi X za $Label..."
    while ((Get-Date) -lt $Deadline) {
        Test-Cancelled
        if (Restore-AdFromGooglePlay $Handle $AdStartedAt) {
            Start-Sleep -Milliseconds 50
            continue
        }
        if (Test-AdCloseReady $Handle) {
            return $true
        }
        Start-Sleep -Milliseconds 50
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
        [scriptblock]$ColorTest
    )
    $rect = Get-WindowRectangle $Handle
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

function Test-FreeButtonReady {
    param([IntPtr]$Handle)
    if ($script:Mode -eq 'OdmoriEkipu') {
        $left = 0.690
        $top = 0.805
        $right = 0.840
        $bottom = 0.925
    }
    else {
        $left = 0.805
        $top = 0.205
        $right = 0.975
        $bottom = 0.285
    }
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
    Add-Log 'OpenCV X detektor je pokrenut.'
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
        return $false
    }

    $x = [double]$result.x
    $y = [double]$result.y
    $polarity = [string]$result.polarity
    $side = if ($null -ne $result.side) { [string]$result.side } else { 'right' }
    $sameTarget = $null -ne $script:XDetectorLastX -and
        [Math]::Abs($x - $script:XDetectorLastX) -le 0.006 -and
        [Math]::Abs($y - $script:XDetectorLastY) -le 0.006 -and
        $polarity -eq $script:XDetectorLastPolarity -and
        $side -eq $script:XDetectorLastSide

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

    $script:DetectedAdCloseX = $x
    $script:DetectedAdCloseY = $y
    Add-Log ("OpenCV X: confidence={0}, oblik={1}, tip={2}, centar={3:N3},{4:N3}" -f $result.score, $result.shape, $polarity, $x, $y)
    return $true
}

function Dismiss-GamePopups {
    param([IntPtr]$Handle)

    Set-Status 'Provjeravam i zatvaram popupove…'
    Wait-Agent 100

    $clearChecks = 0
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        if (Test-ResourcePlusReady $Handle) {
            $clearChecks++
            if ($clearChecks -ge 1) {
                Add-Log 'Glavni ekran je čist; zeleni + je ponovo aktivan.'
                return
            }
            Wait-Agent 50
            continue
        }

        $clearChecks = 0
        switch ($attempt % 4) {
            1 { Send-Escape $Handle }
            2 { Click-Relative $Handle 0.940 0.165 'mogući X na popupu' }
            3 { Click-Relative $Handle 0.500 0.840 'moguće dugme ZATVORI' }
            0 { Click-Relative $Handle 0.900 0.145 'alternativni X na popupu' }
        }
        Wait-Agent 150
    }

    Add-Log 'Nije potvrdjen cist ekran; pokusat cu otvoriti prodavnicu i provjeriti rezultat.'
}

function Open-Store {
    param([IntPtr]$Handle)

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Set-Status "Otvaram prodavnicu preko zelenog + dugmeta (pokušaj $attempt/3)…"
        Click-Relative $Handle 0.651 0.071 'zeleni + za odmore'

        $deadline = (Get-Date).AddMilliseconds(1500)
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
            2 { Click-Relative $Handle 0.940 0.165 'mogući X na popupu' }
            3 { Click-Relative $Handle 0.500 0.840 'moguće dugme ZATVORI' }
            4 { Send-Escape $Handle }
        }
        Wait-Agent 150
    }

    throw 'Nije uspjelo otvoriti prodavnicu nakon zatvaranja popupova.'
}

function Open-TeamRest {
    param([IntPtr]$Handle)

    Set-Status 'Otvaram bocni meni...'
    $form.TopMost = $false
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Wait-Agent 100

    Click-Relative $Handle 0.012 0.092 'bocni meni'
    Wait-Agent 1200
    Click-Relative $Handle 0.120 0.206 'Trening'
    Wait-Agent 2200
    Click-Relative $Handle 0.110 0.907 'Fizio centar'
    Wait-Agent 1200
    Click-Relative $Handle 0.958 0.651 'DMC plus - test'
    Wait-Agent 1200

    $form.TopMost = $true
    Add-Log 'Otvoren je Fizio centar za DMC (test od DMC-a).'
}

function Scroll-PlayerList {
    param(
        [IntPtr]$Handle,
        [ValidateSet('Up', 'Down')]
        [string]$Direction
    )

    $rect = Get-WindowRectangle $Handle
    $x = [int]($rect.Left + (($rect.Right - $rect.Left) * 0.80))
    $y = [int]($rect.Top + (($rect.Bottom - $rect.Top) * 0.55))
    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    [Win32Agent]::SetCursorPos($x, $y) | Out-Null
    Wait-Agent 50

    for ($step = 1; $step -le 6; $step++) {
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

function Wait-ManualTeamRestAd {
    param(
        [IntPtr]$Handle,
        [string]$PlayerLabel
    )

    Set-Status "Cekam BESPLATNO za $PlayerLabel..."
    Wait-ForCondition "BESPLATNO za $PlayerLabel" 30 {
        Test-FreeButtonReady $Handle
    } | Out-Null

    [Win32Agent]::SetForegroundWindow($Handle) | Out-Null
    Set-Status "BESPLATNO je spremno za $PlayerLabel - kliknem automatski." ([System.Drawing.Color]::FromArgb(120, 240, 150))
    Click-Relative $Handle 0.755 0.872 "BESPLATNO - $PlayerLabel"
    $adStartedAt = Get-Date

    Set-Status "Reklama za $PlayerLabel je pokrenuta. Cekam 40 sekundi prije detekcije X-a..."
    $adCloseDeadline = (Get-Date).AddMinutes(5)
    $xDetectionStartsAt = (Get-Date).AddSeconds(40)
    $googlePlayBadgeClicked = $false
    $googlePlayProbeCount = 0
    $firstGooglePlayProbeAt = $adStartedAt.AddSeconds(1)
    $googlePlayReminderAt = (Get-Date).AddSeconds(75)
    $googlePlayReminderShown = $false
    $xDetectionStarted = $false
    $adCloseReady = $false

    while ((Get-Date) -lt $adCloseDeadline) {
        Test-Cancelled
        if (Restore-AdFromGooglePlay $Handle $adStartedAt) {
            $googlePlayBadgeClicked = $true
            Start-Sleep -Milliseconds 50
            continue
        }
        if (-not $googlePlayBadgeClicked -and (Test-AdGooglePlayBadge $Handle)) {
            $googlePlayBadgeClicked = $true
            Set-Status "Kratki Google Play badge za $PlayerLabel je prepoznat - kliknem ga odmah..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            Click-Relative $Handle 0.085 0.058 'Google Play badge u reklami'
            Wait-Agent 500
            continue
        }
        $runGooglePlayProbe = -not $googlePlayBadgeClicked -and
            (Test-PortraitAdWindow $Handle) -and
            (($googlePlayProbeCount -eq 0 -and (Get-Date) -ge $firstGooglePlayProbeAt) -or
             ($googlePlayProbeCount -eq 1 -and (Get-Date) -ge $xDetectionStartsAt))
        if ($runGooglePlayProbe) {
            $googlePlayProbeCount++
            Set-Status "Sigurnosni pokusaj Google Play badgea za $PlayerLabel ($googlePlayProbeCount/2)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
            Click-Relative $Handle 0.085 0.058 'Google Play badge - portretni sigurnosni pokusaj'
            Wait-Agent 350
            continue
        }
        if ((Get-Date) -ge $xDetectionStartsAt) {
            if (-not $xDetectionStarted) {
                $xDetectionStarted = $true
                Set-Status "Proslo je 40 sekundi. Pokrecem detekciju X-a za $PlayerLabel..."
            }
            if (Test-AdCloseReady $Handle) {
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
    for ($closeAttempt = 1; $closeAttempt -le 4; $closeAttempt++) {
        $closeX = if ($null -ne $script:DetectedAdCloseX) { $script:DetectedAdCloseX } else { 0.9525 }
        $closeY = if ($null -ne $script:DetectedAdCloseY) { $script:DetectedAdCloseY } else { 0.077 }
        Click-Relative $Handle $closeX $closeY "X - zatvori reklamu za $PlayerLabel"
        Wait-Agent 800
        if (Restore-AdFromGooglePlay $Handle $adStartedAt) {
            if (-not (Wait-ForAdXAfterGooglePlayReturn $Handle $adCloseDeadline $adStartedAt $PlayerLabel)) {
                throw "Nakon povratka iz Google Play Storea X za $PlayerLabel nije pronadjen."
            }
            continue
        }
        if (-not (Test-AdCloseReady $Handle)) {
            $adClosed = $true
            break
        }
        Add-Log "X klik nije zatvorio reklamu za $PlayerLabel; pokusavam ponovo."
    }

    if (-not $adClosed) {
        throw "X je kliknut, ali reklama za $PlayerLabel nije zatvorena."
    }

    Wait-Agent 1200
    Add-Log "Zavrsen automatski odmor: $PlayerLabel"
}

function Run-TeamRestManualQueue {
    param([IntPtr]$Handle)

    # DMC plus je vec otvoren u Open-TeamRest.
    Wait-ManualTeamRestAd $Handle 'DMC'

    $topRows = @(
        @{ Label = 'MC 1'; Y = 0.728 }
    )
    foreach ($player in $topRows) {
        Click-Relative $Handle 0.958 $player.Y ("plus za {0}" -f $player.Label)
        Wait-Agent 1200
        Wait-ManualTeamRestAd $Handle $player.Label
    }

    Scroll-PlayerList $Handle 'Down'
    $bottomRows = @(
        @{ Label = 'MC 2'; Y = 0.275 },
        @{ Label = 'AML'; Y = 0.352 },
        @{ Label = 'AMR'; Y = 0.430 },
        @{ Label = 'ST'; Y = 0.507 }
    )
    foreach ($player in $bottomRows) {
        Click-Relative $Handle 0.958 $player.Y ("plus za {0}" -f $player.Label)
        Wait-Agent 1200
        Wait-ManualTeamRestAd $Handle $player.Label
    }

    Scroll-PlayerList $Handle 'Up'
    Click-Relative $Handle 0.958 0.345 'plus za DL - ponovo'
    Wait-Agent 1200
    Wait-ManualTeamRestAd $Handle 'DL - ponovo'

    Scroll-PlayerList $Handle 'Down'
    foreach ($player in @(
        @{ Label = 'ST - ponovo'; Y = 0.507 },
        @{ Label = 'AMR - ponovo'; Y = 0.430 },
        @{ Label = 'AML - ponovo'; Y = 0.352 }
    )) {
        Click-Relative $Handle 0.958 $player.Y ("plus za {0}" -f $player.Label)
        Wait-Agent 1200
        Wait-ManualTeamRestAd $Handle $player.Label
    }

    [System.Media.SystemSounds]::Exclamation.Play()
    Set-Status 'Odmor ekipe je zavrsen.' ([System.Drawing.Color]::FromArgb(120, 240, 150))
}

if ($SelfTest) {
    "BlueStacks executable: $(Test-Path -LiteralPath $script:BlueStacksExe)"
    "Configured instance: $script:BlueStacksInstance"
    "Top Eleven shortcut: $(Test-Path -LiteralPath $script:TopElevenShortcut)"
    "Visible BlueStacks window: $((Get-BlueStacksWindow) -ne [IntPtr]::Zero)"
    exit 0
}

function Start-Automation {
    if ($script:Running) { return }
    $script:Running = $true
    $script:Cancelled = $false
    $startButton.Enabled = $false
    $stopButton.Enabled = $true

    try {
        Set-Status 'Pokrećem Top Eleven preko desktop prečice…'
        if (-not (Test-Path -LiteralPath $script:TopElevenShortcut)) {
            throw "Top Eleven desktop prečica nije pronađena: $script:TopElevenShortcut"
        }

        Start-Process -FilePath $script:TopElevenShortcut
        Wait-ForCondition 'pokretanje Top Elevena i BlueStacksa' 120 {
            $script:currentHandle = Get-BlueStacksWindow
            $script:currentHandle -ne [IntPtr]::Zero
        } | Out-Null
        $handle = $script:currentHandle

        [Win32Agent]::ShowWindow($handle, 3) | Out-Null
        [Win32Agent]::SetForegroundWindow($handle) | Out-Null
        Wait-Agent 100

        Set-Status 'Čekam da se Top Eleven učita (do 3 minute)…'
        Wait-ForCondition 'učitavanje početnog ekrana igre' 180 {
            Test-GameHomeLoaded $handle
        } | Out-Null
        Wait-Agent 50

        Dismiss-GamePopups $handle
        if ($script:Mode -eq 'OdmoriEkipu') {
            Open-TeamRest $handle
            Run-TeamRestManualQueue $handle
            return
        }
        else {
            Open-Store $handle
        }

        # === GLAVNA PETLJA - ponavlja dok dugme BESPLATNO ne postane sivo ===
        $freeButtonDisabled = $false
        $totalAdsWatched = 0

        while (-not $freeButtonDisabled -and -not $script:Cancelled) {
            Set-Status 'Čekam da dugme BESPLATNO postane dostupno…'
            Wait-ForCondition 'aktivno dugme BESPLATNO' 90 {
                Test-FreeButtonReady $handle
            } | Out-Null

            [Win32Agent]::SetForegroundWindow($handle) | Out-Null
            Set-Status ("BESPLATNO je spremno - kliknem automatski. (reklama #{0})" -f ($totalAdsWatched + 1)) ([System.Drawing.Color]::FromArgb(120, 240, 150))

            if ($script:Mode -eq 'OdmoriEkipu') {
                Click-Relative $handle 0.755 0.872 'BESPLATNO - odmor GK'
            }
            else {
                Click-Relative $handle 0.890 0.245 'BESPLATNO'
            }
            $adStartedAt = Get-Date

            Set-Status 'Reklama je pokrenuta. Cekam 40 sekundi prije detekcije X-a...'
            $adCloseDeadline = (Get-Date).AddMinutes(5)
            $xDetectionStartsAt = (Get-Date).AddSeconds(40)
            $googlePlayBadgeClicked = $false
            $googlePlayProbeCount = 0
            $firstGooglePlayProbeAt = $adStartedAt.AddSeconds(1)
            $googlePlayReminderAt = (Get-Date).AddSeconds(75)
            $googlePlayReminderShown = $false
            $xDetectionStarted = $false
            $adCloseReady = $false

            while ((Get-Date) -lt $adCloseDeadline) {
                Test-Cancelled
                if (Restore-AdFromGooglePlay $handle $adStartedAt) {
                    $googlePlayBadgeClicked = $true
                    Start-Sleep -Milliseconds 50
                    continue
                }
                if (-not $googlePlayBadgeClicked -and (Test-AdGooglePlayBadge $handle)) {
                    $googlePlayBadgeClicked = $true
                    Set-Status 'Kratki Google Play badge je prepoznat - kliknem ga odmah...' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    Click-Relative $handle 0.085 0.058 'Google Play badge u reklami'
                    Wait-Agent 500
                    continue
                }
                $runGooglePlayProbe = -not $googlePlayBadgeClicked -and
                    (Test-PortraitAdWindow $handle) -and
                    (($googlePlayProbeCount -eq 0 -and (Get-Date) -ge $firstGooglePlayProbeAt) -or
                     ($googlePlayProbeCount -eq 1 -and (Get-Date) -ge $xDetectionStartsAt))
                if ($runGooglePlayProbe) {
                    $googlePlayProbeCount++
                    Set-Status "Sigurnosni pokusaj Google Play badgea ($googlePlayProbeCount/2)..." ([System.Drawing.Color]::FromArgb(255, 210, 100))
                    Click-Relative $handle 0.085 0.058 'Google Play badge - portretni sigurnosni pokusaj'
                    Wait-Agent 350
                    continue
                }
                if ((Get-Date) -ge $xDetectionStartsAt) {
                    if (-not $xDetectionStarted) {
                        $xDetectionStarted = $true
                        Set-Status 'Proslo je 40 sekundi. Pokrecem detekciju X-a...'
                    }
                    if (Test-AdCloseReady $handle) {
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
                throw 'X nije prepoznat u roku od 5 minuta.'
            }

            [Win32Agent]::SetForegroundWindow($handle) | Out-Null
            Set-Status 'X je dostupan — zatvaram reklamu automatski.' ([System.Drawing.Color]::FromArgb(120, 240, 150))

            $adClosed = $false
            for ($closeAttempt = 1; $closeAttempt -le 4; $closeAttempt++) {
                $closeX = if ($null -ne $script:DetectedAdCloseX) { $script:DetectedAdCloseX } else { 0.9525 }
                $closeY = if ($null -ne $script:DetectedAdCloseY) { $script:DetectedAdCloseY } else { 0.077 }
                Click-Relative $handle $closeX $closeY 'X (zatvori reklamu)'
                Wait-Agent 800
                if (Restore-AdFromGooglePlay $handle $adStartedAt) {
                    if (-not (Wait-ForAdXAfterGooglePlayReturn $handle $adCloseDeadline $adStartedAt 'reklamu')) {
                        throw 'Nakon povratka iz Google Play Storea X nije pronadjen.'
                    }
                    continue
                }
                if (-not (Test-AdCloseReady $handle)) { $adClosed = $true; break }
                Add-Log 'X klik nije zatvorio reklamu; pokušavam ponovo.'
            }

            if ($adClosed) {
                $totalAdsWatched++
                Add-Log "Reklama #$totalAdsWatched uspješno zatvorena."
                Wait-Agent 500

                # Provjeri je li dugme BESPLATNO postalo sivo (nedostupno)
                # Nakon zatvaranja reklame, vrati se na ekran prodavnice
                Set-Status 'Provjeravam je li dugme BESPLATNO još uvijek dostupno...'
                
                # Ponekad treba malo vremena da se prodavnica osvježi
                Wait-Agent 200
                
                if ($script:Mode -eq 'OdmoriEkipu') {
                    Click-Relative $handle 0.958 0.269 'GK plus - sljedeci odmor'
                    Wait-Agent 500
                }
                else {
                    # Ako prodavnica nije vidljiva, pokušaj je ponovo otvoriti
                    if (-not (Test-StoreLoaded $handle)) {
                        Add-Log 'Prodavnica nije vidljiva, pokušavam ponovo otvoriti...'
                        Open-Store $handle
                    }
                }

                # Provjeri je li dugme BESPLATNO još uvijek aktivno
                $stillAvailable = Test-FreeButtonReady $handle
                
                if (-not $stillAvailable) {
                    $freeButtonDisabled = $true
                    [System.Media.SystemSounds]::Exclamation.Play()
                    Set-Status "Sve reklame su pogledane! Ukupno: $totalAdsWatched reklama." ([System.Drawing.Color]::FromArgb(120, 240, 150))
                    [System.Windows.Forms.MessageBox]::Show(
                        $form,
                        "Sve dostupne reklame su pogledane!`r`n`r`nUkupno pogledanih reklama: $totalAdsWatched",
                        'Top Eleven Agent - završeno',
                        [System.Windows.Forms.MessageBoxButtons]::OK,
                        [System.Windows.Forms.MessageBoxIcon]::Information
                    ) | Out-Null
                }
                else {
                    Set-Status "Reklama #$totalAdsWatched zatvorena. Čekam sljedeću..." ([System.Drawing.Color]::FromArgb(220, 235, 255))
                    Wait-Agent 500
                    # Nastavi petlju za sljedeću reklamu
                }
            }
            else {
                Set-Status 'X je kliknut, ali reklama možda nije zatvorena — provjerite.' ([System.Drawing.Color]::FromArgb(255, 210, 100))
                # Ako reklama nije zatvorena, možda je potrebna ručna intervencija
                break
            }
        }

        if ($freeButtonDisabled) {
            Set-Status "Sve reklame pogledane! ($totalAdsWatched reklama)" ([System.Drawing.Color]::FromArgb(120, 240, 150))
        }
    }
    catch [System.OperationCanceledException] {
        Set-Status 'Automatizacija je zaustavljena.' ([System.Drawing.Color]::FromArgb(255, 210, 100))
    }
    catch {
        Set-Status "Greška: $($_.Exception.Message)" ([System.Drawing.Color]::FromArgb(255, 120, 120))
        [System.Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, 'Top Eleven Agent - greška', 'OK', 'Error') | Out-Null
    }
    finally {
        Stop-XDetector
        $script:Running = $false
        $startButton.Enabled = $true
        $stopButton.Enabled = $false
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Top Eleven Agent'
$form.Size = New-Object System.Drawing.Size(470, 335)
$form.MinimumSize = New-Object System.Drawing.Size(470, 335)
$form.StartPosition = 'Manual'
$workingArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Location = New-Object System.Drawing.Point(15, ($workingArea.Bottom - $form.Height - 15))
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(24, 29, 45)
$form.ForeColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Text = 'TOP ELEVEN AGENT'
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

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'POKRENI'
$startButton.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
$startButton.Location = New-Object System.Drawing.Point(20, 98)
$startButton.Size = New-Object System.Drawing.Size(205, 42)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(48, 180, 75)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = 'Flat'
$startButton.Add_Click({ Start-Automation })
$form.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'ZAUSTAVI'
$stopButton.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
$stopButton.Location = New-Object System.Drawing.Point(238, 98)
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
$log.Location = New-Object System.Drawing.Point(20, 153)
$log.Size = New-Object System.Drawing.Size(423, 130)
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
[void]$form.ShowDialog()
