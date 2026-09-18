import base64
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")


def function_source(name: str) -> str:
    match = re.search(rf"(?im)^function\s+{re.escape(name)}\s*\{{", SCRIPT)
    if not match:
        raise AssertionError(f"missing function {name}")
    opening = SCRIPT.find("{", match.start())
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(SCRIPT)):
        char = SCRIPT[index]
        if escaped:
            escaped = False
            continue
        if char == "`":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return SCRIPT[match.start() : index + 1]
    raise AssertionError(f"unterminated function {name}")


def run_powershell(command: str):
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if powershell is None:
        raise unittest.SkipTest("PowerShell is required by this Windows-only agent")
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        [powershell, "-NoProfile", "-EncodedCommand", encoded],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


class AdCloseStabilityRegressionTests(unittest.TestCase):
    def run_confirmation(self, initial):
        command = f"""
$ErrorActionPreference = 'Stop'
$script:AiTopElevenReturned = $false
$script:DetectedAdCloseX = {initial['x']}
$script:DetectedAdCloseY = {initial['y']}
$script:DetectedAdCloseKind = 'close'
$script:DetectedAdCloseLocallyVerified = ${str(initial['verified']).lower()}
function Add-Log {{ param([string]$Text) }}
function Test-AiOnlyAdControlReady {{
    throw 'Confirm function must not make a second AI request'
}}
function Wait-ForAdExitOrControl {{ return 'unknown' }}
{function_source('Confirm-AiAdCloseImmediatelyBeforeClick')}
$state = Confirm-AiAdCloseImmediatelyBeforeClick ([IntPtr]::Zero) 'test reklama'
[PSCustomObject]@{{
    state = $state
    x = $script:DetectedAdCloseX
    y = $script:DetectedAdCloseY
    kind = $script:DetectedAdCloseKind
    verified = [bool]$script:DetectedAdCloseLocallyVerified
}} | ConvertTo-Json -Compress
"""
        completed = run_powershell(command)
        self.assertEqual(0, completed.returncode, completed.stderr)
        return json.loads(completed.stdout.strip())

    def test_one_locally_verified_ai_close_is_immediately_ready(self):
        result = self.run_confirmation({"x": 0.954, "y": 0.098, "verified": True})
        self.assertEqual("close", result["state"])
        self.assertAlmostEqual(0.954, result["x"])
        self.assertAlmostEqual(0.098, result["y"])
        self.assertTrue(result["verified"])

    def test_unverified_ai_coordinate_is_not_clicked(self):
        result = self.run_confirmation({"x": 0.952, "y": 0.580, "verified": False})
        self.assertEqual("not_confirmed", result["state"])

    def run_retry_monitor(self, outcome):
        command = f"""
$ErrorActionPreference = 'Stop'
$script:DetectedAdCloseKind = 'close'
$script:DetectedAdCloseX = 0.95
$script:DetectedAdCloseY = 0.10
$script:DetectedAdCloseLocallyVerified = $false
$script:VisionAiProbeIntervalSeconds = 12
$script:ProbeCount = 0
function Add-Log {{ param([string]$Text) }}
function Test-Cancelled {{}}
function Wait-Agent {{ param($Milliseconds) }}
function Restore-AdFromGooglePlay {{ return $false }}
function Test-TopElevenReturnedAfterAd {{ return $false }}
function Test-AiOnlyAdControlReady {{
    $script:ProbeCount++
    if ($null -ne $script:DetectedAdCloseX) {{ throw 'Stale coordinate survived into follow-up' }}
    $script:AiTopElevenReturned = ${str(outcome == 'returned').lower()}
    if ('{outcome}' -eq 'close') {{
        $script:DetectedAdCloseX = 0.88
        $script:DetectedAdCloseY = 0.12
        $script:DetectedAdCloseKind = 'close'
        $script:DetectedAdCloseLocallyVerified = $true
        return $true
    }}
    return $false
}}
{function_source('Wait-ForAdExitOrControl')}
{function_source('Confirm-AiAdCloseImmediatelyBeforeClick')}
$state = Confirm-AiAdCloseImmediatelyBeforeClick ([IntPtr]::Zero) 'retry' (Get-Date)
[PSCustomObject]@{{ state = $state; probes = $script:ProbeCount; x = $script:DetectedAdCloseX }} | ConvertTo-Json -Compress
"""
        completed = run_powershell(command)
        self.assertEqual(0, completed.returncode, completed.stderr)
        return json.loads(completed.stdout.strip())

    def test_retry_actually_probes_and_uses_ai_return_without_close(self):
        result = self.run_retry_monitor("returned")
        self.assertEqual("returned", result["state"])
        self.assertEqual(1, result["probes"])
        self.assertIsNone(result["x"])

    def test_retry_uses_new_verified_close_in_same_iteration(self):
        result = self.run_retry_monitor("close")
        self.assertEqual("close", result["state"])
        self.assertEqual(1, result["probes"])
        self.assertAlmostEqual(0.88, result["x"])

    def test_ai_fallback_is_rejected_before_preclick(self):
        command = f"""
$ErrorActionPreference = 'Stop'
function Add-Log {{ param([string]$Text) }}
function Invoke-VisionAnalysis {{ return $script:VisionResult }}
{function_source('Test-AiOnlyAdControlReady')}
$script:VisionCacheByState = @{{}}
$script:VisionResult = [PSCustomObject]@{{
    accepted = $true
    decision = [PSCustomObject]@{{
        screenType = 'ad'
        topElevenReturned = $false
        recommendedAction = 'click_close'
        control = [PSCustomObject]@{{ x = 0.952; y = 0.580; confidence = 0.99 }}
    }}
    closeRefinement = [PSCustomObject]@{{ applied = $false; fallbackToAiCoordinate = $true }}
}}
$ready = Test-AiOnlyAdControlReady ([IntPtr]::Zero) 'ad_control_ai_only_test' -ForceRefresh
[PSCustomObject]@{{
    ready = [bool]$ready
    xIsNull = $null -eq $script:DetectedAdCloseX
    yIsNull = $null -eq $script:DetectedAdCloseY
    kindIsNull = $null -eq $script:DetectedAdCloseKind
    verified = [bool]$script:DetectedAdCloseLocallyVerified
}} | ConvertTo-Json -Compress
"""
        completed = run_powershell(command)
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout.strip())
        self.assertFalse(result["ready"])
        self.assertTrue(result["xIsNull"])
        self.assertTrue(result["yIsNull"])
        self.assertTrue(result["kindIsNull"])
        self.assertFalse(result["verified"])

    def test_wake_probe_hands_verified_close_to_click_flow(self):
        start = SCRIPT.index("if (-not (Test-AdWakeTapAllowed $handle $adStartedAt 'Reklama za 25 zelenih'))")
        end = SCRIPT.index("$adWakeTapCount++", start)
        body = SCRIPT[start:end]
        self.assertIn("$script:DetectedAdCloseKind -eq 'close'", body)
        self.assertIn("$script:DetectedAdCloseLocallyVerified", body)
        close_ready = body.index("$adCloseReady = $true")
        self.assertLess(body.index("break", close_ready), body.index("$reuseWakeAnalysis = $true"))
        returned = body.index("if ($script:AiTopElevenReturned)")
        self.assertLess(body.index("$adAlreadyExited = $true", returned), close_ready)
        self.assertLess(body.index("break", returned), close_ready)


if __name__ == "__main__":
    unittest.main()
