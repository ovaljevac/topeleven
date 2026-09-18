# Durable progress contains semantic checkpoints only, never click coordinates.
function Save-AgentCheckpoint {
    if ($null -eq $script:Checkpoint -or $script:DryRun -or $script:Calibration) { return }
    $temporary = "$($script:CheckpointPath).$PID.tmp"
    try {
        $script:Checkpoint.UpdatedUtc = [datetime]::UtcNow.ToString('o')
        $directory = Split-Path -Parent $script:CheckpointPath
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
        [System.IO.File]::WriteAllText($temporary, ($script:Checkpoint | ConvertTo-Json -Depth 6), [System.Text.UTF8Encoding]::new($false))
        if ([System.IO.File]::Exists($script:CheckpointPath)) {
            [System.IO.File]::Replace($temporary, $script:CheckpointPath, "$($script:CheckpointPath).bak")
        } else { [System.IO.File]::Move($temporary, $script:CheckpointPath) }
    } catch { Add-Log "Napredak nije sacuvan: $($_.Exception.Message). Nastavak ce imati samo ranije sacuvane potvrde." }
}

function Initialize-AgentCheckpoint {
    param([bool]$ResumeRequested)
    $script:Checkpoint = $null
    $script:ResumeNeedsPreparation = $false
    if ($script:Mode -in @('Start', 'Restart') -or $script:DryRun -or $script:Calibration) { return }
    $settings = "$PSScriptRoot|$($script:BlueStacksInstance)|$($script:Mode)"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($settings)))).Replace('-', '').Substring(0,24) }
    finally { $sha.Dispose() }
    $root = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'TopElevenAgent\checkpoints'
    $script:CheckpointPath = Join-Path $root "$key.json"
    $configHasher = [Security.Cryptography.SHA256]::Create()
    try { $configHash = [BitConverter]::ToString($configHasher.ComputeHash([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'config.json')))).Replace('-', '') }
    finally { $configHasher.Dispose() }
    $day = (Get-Date).ToString('yyyy-MM-dd')
    $validStages = @('Mourinho', 'Top Eleven TV', 'Put saveza', 'Kampus', 'Uzmi 25 zelenih', 'Trening igraca', 'Odmori igrace')
    if ($ResumeRequested) {
        if (-not (Test-Path -LiteralPath $script:CheckpointPath)) { throw 'Nema sacuvanog napretka za ovu skriptu i BlueStacks instancu.' }
        $saved = Get-Content -Raw -LiteralPath $script:CheckpointPath | ConvertFrom-Json
        if ($saved.Version -ne 1 -or $saved.Mode -ne $script:Mode -or $saved.Instance -ne $script:BlueStacksInstance -or
            $saved.Day -ne $day -or $saved.ConfigHash -ne $configHash -or
            @($saved.CompletedStages | Where-Object { $_ -notin $validStages }).Count -gt 0 -or
            @($saved.CompletedPlayers | Where-Object { $_ -notin @($script:TeamRestQueue.Key) }).Count -gt 0 -or
            $saved.TeamRestStart -notin @($script:TeamRestQueue.Key) -or
            [int]$saved.TrainingCycles -lt 0 -or [int]$saved.TrainingCycles -gt 100 -or
            $saved.CombinedStart -notin @('Mourinho','TV','PutSaveza','Kampus','Zeleni')) {
            throw 'Sacuvani napredak nije za danasnju sesiju/konfiguraciju ili nije ispravan; pokreni novu sesiju.'
        }
        $script:Checkpoint = $saved
        $script:CombinedStartStage = [string]$saved.CombinedStart
        $script:TeamRestStartKey = [string]$saved.TeamRestStart
        $script:ResumeNeedsPreparation = $true
        Add-Log "Nastavljam sacuvanu sesiju: faza=$($saved.Stage), posljednja potvrda=$($saved.Step). Koordinate se ne ucitavaju."
    } else {
        $script:Checkpoint = [PSCustomObject]@{
            Version=1; Mode=$script:Mode; Instance=$script:BlueStacksInstance; Day=$day; ConfigHash=$configHash
            CombinedStart=$script:CombinedStartStage; TeamRestStart=$script:TeamRestStartKey
            Stage=''; Step='session_started'; PendingAction=''; UpdatedUtc=''; CompletedStages=@(); CompletedPlayers=@(); TrainingCycles=0
        }
        Save-AgentCheckpoint
    }
}

function Set-AgentCheckpointStep {
    param([string]$Step)
    if ($null -eq $script:Checkpoint) { return }
    $script:Checkpoint.Step = $Step
    $script:Checkpoint.PendingAction = ''
    Save-AgentCheckpoint
}

function Set-AgentPendingAction {
    param([string]$Action)
    if ($null -eq $script:Checkpoint) { return }
    $script:Checkpoint.PendingAction = $Action
    Save-AgentCheckpoint
}

function Prepare-AgentResume {
    param([IntPtr]$Handle)
    if (-not $script:ResumeNeedsPreparation) { return $Handle }
    Test-Cancelled
    # Nastavak prihvata trenutno otvoreni ekran igre. Pojedinacna faza sama
    # pronalazi svoj ekran; genericka "Top Eleven je ucitan" kapija vise ne
    # smije izazvati restart samo zato sto korisnik stoji u Prodavnici.
    Add-Log 'Nastavak: koristim trenutno otvoreni ekran bez genericke provjere pocetnog Top Eleven ekrana.'
    $script:ResumeNeedsPreparation = $false
    return $Handle
}

function Save-AgentFailureEvidence {
    param([string]$Stage, [System.Exception]$Failure)
    if ($script:DryRun -or $script:Calibration -or $script:ErrorCaptureCount -ge 8) { return }
    if ($script:LastEvidenceMessage -eq $Failure.Message) { return }
    $script:LastEvidenceMessage = $Failure.Message
    $script:ErrorCaptureCount++
    try {
        $directory = if ($script:ExternalLogPath) { "$($script:ExternalLogPath).errors" } else {
            Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) "TopElevenAgent\logs\local-$PID.errors"
        }
        [IO.Directory]::CreateDirectory($directory) | Out-Null
        $id = [guid]::NewGuid().ToString('N')
        $imagePath = Join-Path $directory "$id.png"
        $captureError = ''
        $captured = $false
        $bitmap = $null; $graphics = $null; $dc = [IntPtr]::Zero
        try {
            $windowHandle = Get-BlueStacksWindow -RequireConfiguredInstance
            if ($windowHandle -eq [IntPtr]::Zero) { throw 'BlueStacks prozor nije dostupan.' }
            $rect = Get-WindowRectangle $windowHandle
            $width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
            if ($width -le 0 -or $height -le 0 -or $width -gt 8192 -or $height -gt 8192) { throw 'Neispravne dimenzije prozora.' }
            $bitmap = [Drawing.Bitmap]::new($width, $height)
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            $dc = $graphics.GetHdc()
            # Print only this window: never copy the desktop or foreground overlays.
            if (-not [Win32Agent]::PrintWindow($windowHandle, $dc, 2)) { throw 'Windows nije uspio snimiti BlueStacks prozor.' }
            $graphics.ReleaseHdc($dc); $dc = [IntPtr]::Zero
            $visiblePixels = 0
            for ($row=1; $row -lt 16; $row++) {
                for ($column=1; $column -lt 16; $column++) {
                    $sample = $bitmap.GetPixel([int]($width*$column/16), [int]($height*$row/16))
                    if ([int]$sample.R + [int]$sample.G + [int]$sample.B -gt 12) { $visiblePixels++ }
                }
            }
            if ($visiblePixels -eq 0) { throw 'BlueStacks je vratio praznu crnu sliku; desktop se ne snima kao zamjena.' }
            $bitmap.Save($imagePath, [Drawing.Imaging.ImageFormat]::Png)
            $captured = $true
        } catch { $captureError = $_.Exception.Message }
        finally {
            if ($dc -ne [IntPtr]::Zero -and $null -ne $graphics) { $graphics.ReleaseHdc($dc) }
            if ($null -ne $graphics) { $graphics.Dispose() }
            if ($null -ne $bitmap) { $bitmap.Dispose() }
        }
        $event = @{ Version=1; Stage=$Stage; Message=$Failure.Message; Step=$script:Checkpoint.Step; Expected=$script:LastStatusText; Action=$script:Checkpoint.PendingAction
            Captured=$captured; CaptureError=$captureError; CreatedUtc=[datetime]::UtcNow.ToString('o') }
        # Publish metadata last so Discord never observes a half-written image.
        $path = Join-Path $directory "$id.json"
        [IO.File]::WriteAllText("$path.tmp", ($event | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        [IO.File]::Move("$path.tmp", $path)
        Add-Log "Izvjestaj greske sacuvan: $path"
    } catch { Add-Log "Nije moguce sacuvati screenshot greske: $($_.Exception.Message)" }
}
