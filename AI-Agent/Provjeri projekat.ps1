param([switch]$NoGui)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms

function Test-PythonRuntimePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    try {
        & $Path -c 'import sys; raise SystemExit(0 if sys.version_info.major >= 3 else 1)' 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-PythonRuntime {
    $profileCandidates = @(
        [string]$env:USERPROFILE,
        [string][Environment]::GetFolderPath('UserProfile')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
    $candidates = @(
        (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
        (Join-Path $PSScriptRoot 'venv\Scripts\python.exe')
    ) + @($profileCandidates | ForEach-Object {
        Join-Path $_ '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    })
    foreach ($candidate in $candidates) {
        if (Test-PythonRuntimePath $candidate) { return $candidate }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $command -and (Test-PythonRuntimePath ([string]$command.Source))) { return $command.Source }
    return $null
}

$requiredFiles = @(
    'AgentPersistence.ps1',
    'agent_artifacts.py',
    'TopElevenAgent.ps1',
    'TopElevenManager.ps1',
    'VisionAgent.py',
    'XDetector.py',
    'config.json',
    'ai_config.json',
    'requirements.txt'
)
$powerShellFiles = @(
    'AgentPersistence.ps1',
    'TopElevenAgent.ps1',
    'TopElevenManager.ps1',
    'Postavi Gemini API kljuc.ps1',
    'Testiraj Gemini.ps1',
    'Provjeri projekat.ps1'
)
$jsonFiles = @('config.json', 'ai_config.json')
$failures = [System.Collections.Generic.List[string]]::new()
$details = [System.Collections.Generic.List[string]]::new()
$commandOutput = [System.Collections.Generic.List[string]]::new()

function Invoke-ProjectCheckCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        # unittest namjerno pise status na stderr i kada svi testovi prodju.
        # Native stderr zato nije PowerShell izuzetak; izlazni kod je autoritet.
        $ErrorActionPreference = 'Continue'
        $output = & $Executable @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    }
    catch {
        $output = $_ | Out-String
        $exitCode = -1
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    $commandOutput.Add("===== $Label =====`r`n$output")
    if ($exitCode -eq 0) {
        $details.Add("OK: $Label")
    }
    else {
        $failures.Add("$Label nije prosao (kod $exitCode).")
    }
}

foreach ($relativePath in $requiredFiles) {
    $path = Join-Path $PSScriptRoot $relativePath
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $details.Add("OK fajl: $relativePath")
    }
    else {
        $failures.Add("Nedostaje obavezni fajl: $relativePath")
    }
}

foreach ($relativePath in $powerShellFiles) {
    $path = Join-Path $PSScriptRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $path,
        [ref]$tokens,
        [ref]$parseErrors
    )
    if (@($parseErrors).Count -gt 0) {
        foreach ($parseError in @($parseErrors)) {
            $failures.Add("PowerShell sintaksa $relativePath`: $($parseError.Message)")
        }
    }
    else {
        $details.Add("OK PowerShell: $relativePath")
    }
}

foreach ($relativePath in $jsonFiles) {
    $path = Join-Path $PSScriptRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    try {
        Get-Content -Raw -LiteralPath $path | ConvertFrom-Json | Out-Null
        $details.Add("OK JSON: $relativePath")
    }
    catch {
        $failures.Add("Neispravan JSON $relativePath`: $($_.Exception.Message)")
    }
}

$python = Resolve-PythonRuntime
if ($null -eq $python) {
    $failures.Add('Python 3 nije pronadjen (.venv, ugradjeni runtime ili PATH).')
}
else {
    Invoke-ProjectCheckCommand 'Python sintaksa' $python @(
        '-m', 'py_compile',
        (Join-Path $PSScriptRoot 'VisionAgent.py'),
        (Join-Path $PSScriptRoot 'XDetector.py')
    )
    Invoke-ProjectCheckCommand 'Python test suite' $python @(
        '-m', 'unittest', 'discover', '-s', (Join-Path $PSScriptRoot 'tests'), '-v'
    )

    $regressionArchive = Join-Path (Split-Path -Parent $PSScriptRoot) 'ss.zip'
    if (Test-Path -LiteralPath $regressionArchive -PathType Leaf) {
        Invoke-ProjectCheckCommand 'Screenshot regresija' $python @(
            (Join-Path $PSScriptRoot 'regression\run_opencv_regression.py'),
            '--zip', $regressionArchive
        )
    }
    else {
        $details.Add('PRESKOCENO: screenshot regresija (opcionalni ss.zip nije pronadjen).')
    }
}

$powerShellCommand = Get-Command powershell.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $powerShellCommand) {
    $failures.Add('Windows PowerShell nije pronadjen.')
}
else {
    $powerShell = $powerShellCommand.Source
    Invoke-ProjectCheckCommand 'TopElevenAgent SelfTest' $powerShell @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        (Join-Path $PSScriptRoot 'TopElevenAgent.ps1'), '-SelfTest'
    )
    Invoke-ProjectCheckCommand 'TopElevenManager SelfTest' $powerShell @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        (Join-Path $PSScriptRoot 'TopElevenManager.ps1'), '-SelfTest'
    )
}

$logsRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'TopElevenAgent\logs'
[System.IO.Directory]::CreateDirectory($logsRoot) | Out-Null
$logPath = Join-Path $logsRoot ("project-check-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$report = @(
    "Top Eleven project check - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    '',
    ($details -join [Environment]::NewLine),
    '',
    'GRESKE:',
    $(if ($failures.Count -eq 0) { 'Nema.' } else { $failures -join [Environment]::NewLine }),
    '',
    'IZLAZ KOMANDI:',
    ($commandOutput -join [Environment]::NewLine)
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($logPath, $report, [System.Text.UTF8Encoding]::new($false))

if ($failures.Count -eq 0) {
    if ($NoGui) {
        Write-Host "Projekat je ispravan. Izvjestaj: $logPath" -ForegroundColor Green
        exit 0
    }
    [System.Windows.Forms.MessageBox]::Show(
        "Projekat je ispravan. Sve lokalne provjere su prosle.`r`n`r`nIzvjestaj:`r`n$logPath",
        'Top Eleven Agent - provjera projekta',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
    exit 0
}

if ($NoGui) {
    Write-Host "Provjera je pronasla $($failures.Count) problema. Detalji: $logPath" -ForegroundColor Red
    foreach ($failure in $failures) { Write-Host "- $failure" -ForegroundColor Red }
    exit 1
}

[System.Windows.Forms.MessageBox]::Show(
    "Provjera je pronasla $($failures.Count) problema.`r`n`r`n$($failures -join "`r`n")`r`n`r`nDetalji:`r`n$logPath",
    'Top Eleven Agent - provjera projekta',
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Error
) | Out-Null
exit 1
