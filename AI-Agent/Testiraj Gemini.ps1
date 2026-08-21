$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime nije pronadjen: $python"
}

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
$testImagePath = Join-Path ([Environment]::GetFolderPath('MyPictures')) 'Screenshots\Screenshot 2026-08-06 003400.png'
$testImage = Get-Item -LiteralPath $testImagePath -ErrorAction SilentlyContinue

if ($null -eq $testImage) {
    Write-Host 'API kljuc je pronadjen. Nema screenshota za pravi vision poziv.' -ForegroundColor Yellow
}
else {
    Write-Host "Saljem jedan testni screenshot: $($testImage.Name)" -ForegroundColor Cyan
    $responseText = & $python (Join-Path $root 'VisionAgent.py') --config (Join-Path $root 'ai_config.json') --image $testImage.FullName --expected-state ad_control
    if ($LASTEXITCODE -ne 0) {
        throw "Gemini vision test je zavrsio kodom $LASTEXITCODE."
    }
    $response = $responseText | ConvertFrom-Json
    if (-not $response.ok) {
        throw $response.error
    }
    Write-Host "Pravi Gemini vision poziv je uspio za $($response.latencyMs) ms." -ForegroundColor Green
    Write-Host "Odluka: $($response.decision.recommendedAction); ekran: $($response.decision.screenType)" -ForegroundColor Green
}
Read-Host 'Pritisni Enter za zatvaranje'
