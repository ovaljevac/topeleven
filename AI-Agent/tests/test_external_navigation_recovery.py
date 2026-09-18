import base64
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "TopElevenAgent.ps1"
SCRIPT = AGENT_PATH.read_text(encoding="utf-8-sig")


def function_source(name: str) -> str:
    """Return one complete PowerShell function using brace balancing."""

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


def function_body(name: str) -> str:
    source = function_source(name)
    return source[source.index("{") + 1 : source.rindex("}")]


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


class RemovedActivityTests(unittest.TestCase):
    def test_no_activity_queries_or_log_readers_remain(self):
        for forbidden in ('Get-BlueStacksForegroundState', 'Get-BlueStacksAdbForegroundState', 'Get-RecentBlueStacksActivityRecord', "'dumpsys'", 'MainPlayerNativeActivity'):
            self.assertNotIn(forbidden, SCRIPT)


class BlueStacksAdbContractTests(unittest.TestCase):

    def resolve_adb_serial(self, devices_output: str, config_text: str):
        devices_fixture = json.dumps(devices_output)
        config_fixture = json.dumps(config_text)
        command = f"""
$ErrorActionPreference = 'Stop'
$script:BlueStacksAdbSerial = $null
$script:BlueStacksAdbSerialCheckedAt = [datetime]::MinValue
$script:BlueStacksInstance = 'Pie64'
$script:BlueStacksConfigPath = 'mock.conf'
function Invoke-BlueStacksAdbCommand {{
    return [PSCustomObject]@{{ Success = $true; Output = (ConvertFrom-Json @'
{devices_fixture}
'@); Error = '' }}
}}
function Test-Path {{ return $true }}
function Get-Content {{ return (ConvertFrom-Json @'
{config_fixture}
'@) }}
{function_source('Resolve-BlueStacksAdbSerial')}
$result = Resolve-BlueStacksAdbSerial
if ($null -eq $result) {{ 'null' }} else {{ [string]$result }}
"""
        completed = run_powershell(command)
        self.assertEqual(0, completed.returncode, completed.stderr)
        return completed.stdout.strip()




    def test_adb_process_io_is_bounded_and_drains_both_streams(self):
        invoke = function_body("Invoke-BlueStacksAdbCommand")
        self.assertIn("ReadToEndAsync()", invoke)
        self.assertIn("RedirectStandardOutput = $true", invoke)
        self.assertIn("RedirectStandardError = $true", invoke)
        self.assertIn("WaitForExit($TimeoutMs)", invoke)
        self.assertIn("$process.Kill()", invoke)

    def test_back_prefers_exact_adb_device_and_retains_escape_fallback(self):
        back = function_body("Send-BlueStacksBack")
        resolve = back.index("Resolve-BlueStacksAdbSerial")
        adb_key = back.index("KEYCODE_BACK", resolve)
        adb_success = back.index("if ($adbBack.Success)", adb_key)
        success_return = back.index("return", adb_success)
        escape = back.index("[Win32Agent]::keybd_event", success_return)
        self.assertLess(resolve, adb_key)
        self.assertLess(adb_key, success_return)
        self.assertLess(success_return, escape)


    def test_serial_resolution_is_fail_closed_with_multiple_devices(self):
        resolver = function_body("Resolve-BlueStacksAdbSerial")
        self.assertIn("$deviceSerials.Count -eq 1", resolver)
        self.assertIn("$script:BlueStacksAdbSerial = $null", resolver)
        self.assertNotRegex(resolver, r"(?i)deviceSerials\s*\[\s*0\s*\].*Count\s+-gt\s+1")

    def test_serial_resolution_selects_configured_instance_among_multiple_devices(self):
        result = self.resolve_adb_serial(
            "List of devices attached\r\nemulator-5554\tdevice\r\nemulator-5564\tdevice\r\n",
            'bst.instance.Pie64.adb_port="5555"',
        )
        self.assertEqual("emulator-5554", result)

    def test_serial_resolution_refuses_ambiguous_unmatched_devices(self):
        result = self.resolve_adb_serial(
            "List of devices attached\r\nemulator-5554\tdevice\r\nemulator-5564\tdevice\r\n",
            'bst.instance.Pie64.adb_port="5599"',
        )
        self.assertEqual("null", result)


class ExternalNavigationRecoveryContractTests(unittest.TestCase):
    def test_external_restore_supports_store_and_chrome_and_sends_android_back(self):
        restore = function_body("Restore-AdFromGooglePlay")
        self.assertIn("Test-AiExternalNavigationVisible", restore)
        self.assertNotIn("Get-BlueStacksForegroundState", restore)
        self.assertIn("Send-BlueStacksBack $Handle", restore)
        self.assertIn("$script:ExternalNavigationBackAttempts", restore)
        self.assertNotIn("$recentAiPlayClick", restore)

    def test_current_external_package_is_not_ignored_as_an_already_handled_event(self):
        restore = function_body("Restore-AdFromGooglePlay")
        package_gate_end = restore.index("$externalByAi")
        package_gate = restore[:package_gate_end]
        self.assertNotIn(
            "LastHandledGooglePlayEvent",
            package_gate,
            "A still-foreground Store/Chrome record must keep the restore flow active; "
            "cooldown/back-attempt limits already prevent a Back storm.",
        )

    def test_after_back_prefers_current_adb_state_and_keeps_visual_fallback(self):
        restore = function_body("Restore-AdFromGooglePlay")
        after_back = restore[restore.index("Send-BlueStacksBack $Handle") :]
        self.assertNotIn("Get-BlueStacksForegroundState", after_back)
        self.assertIn(
            "Test-AiExternalNavigationVisible $Handle $AdStartedAt -ForceRefresh",
            after_back,
            "AI must remain available when current ADB state cannot be read.",
        )

    def test_unknown_ai_after_back_uses_backoff_instead_of_a_tight_loop(self):
        restore = function_body("Restore-AdFromGooglePlay")
        null_branch = re.search(
            r"(?is)if\s*\(\$null\s+-eq\s+\$aiAfterBack\)\s*\{(?P<body>.*?)\}",
            restore,
        )
        self.assertIsNotNone(null_branch)
        self.assertRegex(null_branch.group("body"), r"(?i)Wait-Agent\s+[5-9]\d{2,}")

    def test_game_action_preflight_restores_external_navigation(self):
        helper = function_body("Restore-ExternalNavigationBeforeGameAction")
        self.assertIn("Restore-AdFromGooglePlay", helper)
        self.assertIn("Invoke-VisionAnalysis", helper)
        self.assertRegex(helper, r"(?i)(deadline|attempt)")
        self.assertRegex(helper, r"(?i)(return\s+\$true|throw)")

    def test_stale_ad_activity_cannot_invent_an_ad_over_two_home_frames(self):
        helper = function_body("Restore-ExternalNavigationBeforeGameAction")
        self.assertIn("Test-TopElevenReturnedAfterAd", helper)
        self.assertNotIn("Activity", helper)
        self.assertLess(helper.index("Test-TopElevenReturnedAfterAd"), helper.index("Watch-TVAdvertisement"))

        open_store = function_body("Open-Store")
        restore_pos = open_store.index("Restore-ExternalNavigationBeforeGameAction")
        first_game_click = open_store.index("Click-Relative")
        self.assertLess(
            restore_pos,
            first_game_click,
            "Open-Store must leave Play Store/Chrome before clicking game coordinates.",
        )

    def test_campus_post_ad_click_has_external_navigation_preflight(self):
        campus = function_body("Invoke-CampusStripMaintenance")
        self.assertIn("Watch-TVAdvertisement $Handle $false 'campus'", campus)
        self.assertIn("Wait-CampusFlowState $Handle @('campus_detail')", campus)
        self.assertIn("$fresh.objectStrip.verified", campus)
        self.assertLess(campus.index("$fresh.objectStrip.verified"), campus.index("Click-Relative"))
        self.assertNotIn("zatvori detalj", campus)

    def test_ad_watchers_prioritize_external_navigation_before_return_detection(self):
        tv = function_body("Watch-TVAdvertisement")
        tv_loop = tv[tv.index("while ((Get-Date) -lt $deadline)") :]
        self.assertLess(
            tv_loop.index("Restore-AdFromGooglePlay"),
            tv_loop.index("Test-TopElevenReturnedAfterAd"),
        )

        start = function_body("Start-Automation")
        green = start[start.index("while ((Get-Date) -lt $adCloseDeadline)") :]
        self.assertLess(
            green.index("Restore-AdFromGooglePlay"),
            green.index("Test-AiOnlyAdControlReady"),
        )

        exit_wait = function_body("Wait-ForAdExitOrControl")
        exit_loop = exit_wait[exit_wait.index("while ((Get-Date) -lt $deadline)") :]
        self.assertLess(
            exit_loop.index("Restore-AdFromGooglePlay"),
            exit_loop.index("Test-TopElevenReturnedAfterAd"),
            "Store/Chrome must be handled before any visual return classifier.",
        )

    def test_return_requires_current_main_activity_and_resource_header(self):
        returned = function_body("Test-TopElevenReturnedAfterAd")
        self.assertNotIn("MainPlayerNativeActivity", returned)
        self.assertIn("Test-StoreReturnVisualProof", returned)
        self.assertNotRegex(
            returned,
            r"if\s*\(Test-TopElevenResourceHeaderReady[^\r\n]+\)\s*\{\s*return\s+\$true",
        )


if __name__ == "__main__":
    unittest.main()
