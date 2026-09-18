$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

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
        (Join-Path $root '.venv\Scripts\python.exe'),
        (Join-Path $root 'venv\Scripts\python.exe')
    ) + @($profileCandidates | ForEach-Object {
        Join-Path $_ '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    })
    foreach ($candidate in $candidates) {
        if (Test-PythonRuntimePath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $command -and (Test-PythonRuntimePath ([string]$command.Source))) {
        return $command.Source
    }
    throw 'Python runtime nije pronadjen. Instaliraj Python 3 ili pokreni agent kroz njegov standardni launcher.'
}

$python = Resolve-PythonRuntime

$request = '{"health":true}'
$result = $request | & $python (Join-Path $root 'VisionAgent.py') --config (Join-Path $root 'ai_config.json') --server
if ($LASTEXITCODE -ne 0) {
    throw "VisionAgent je zavrsio kodom $LASTEXITCODE."
}

$health = $result | ConvertFrom-Json
if (-not $health.ok) {
    throw $health.error
}
if (-not $health.credentialsAvailable) {
    throw 'Gemini kljuc nije pronadjen. Prvo pokreni Postavi Gemini API kljuc.cmd.'
}

Write-Host "Gemini konfiguracija je spremna: $($health.model)" -ForegroundColor Green
$testImage = Get-Item -LiteralPath (Join-Path $root 'Kampus\4.png') -ErrorAction Stop

Write-Host "Saljem jedan testni screenshot iz projekta: $($testImage.Name)" -ForegroundColor Cyan
$responseText = & $python (Join-Path $root 'VisionAgent.py') --config (Join-Path $root 'ai_config.json') --image $testImage.FullName --expected-state campus_incomplete_building_smoke_test
if ($LASTEXITCODE -ne 0) {
    throw "Gemini vision test je zavrsio kodom $LASTEXITCODE."
}
$response = $responseText | ConvertFrom-Json
if (-not $response.ok) {
    throw $response.error
}
Write-Host "Pravi Gemini vision poziv je uspio za $($response.latencyMs) ms." -ForegroundColor Green
if (-not [string]::IsNullOrWhiteSpace([string]$response.modelUsed)) {
    Write-Host "Model koji je stvarno odgovorio: $($response.modelUsed)" -ForegroundColor Green
}
Write-Host "Odluka: $($response.decision.recommendedAction); ekran: $($response.decision.screenType)" -ForegroundColor Green
Read-Host 'Pritisni Enter za zatvaranje'
