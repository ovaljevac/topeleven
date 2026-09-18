import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")


def function_body(name: str) -> str:
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
                return SCRIPT[opening + 1:index]
    raise AssertionError(f"unterminated function {name}")


class AgentCoreSafetyContractTests(unittest.TestCase):
    def test_child_process_io_is_bounded_and_stderr_is_drained(self):
        reader = function_body("Read-AgentProcessLine")
        self.assertIn("ReadLineAsync()", reader)
        self.assertIn("$deadline", reader)
        self.assertIn("Stop-AgentProcessAfterIoFailure", reader)
        self.assertNotIn("StandardOutput.ReadLine()", SCRIPT)
        self.assertGreaterEqual(SCRIPT.count("BeginErrorReadLine()"), 2)
        self.assertIn("$script:VisionResponseTimeoutSeconds = 60", SCRIPT)

    def test_discord_restart_mode_uses_verified_recovery_without_ai(self):
        start = function_body("Start-Automation")
        self.assertIn("$script:Mode -eq 'Restart'", start)
        self.assertIn("Restart-TopElevenForStageRetry 'Discord restart'", start)
        self.assertIn("$script:VisionEnabled = $false", start)
        self.assertIn("Top Eleven je uspjesno restartovan", start)

    def test_discord_start_mode_never_restarts_an_open_instance(self):
        start = function_body("Start-Automation")
        start_mode = start[start.index("$script:Mode -eq 'Start'"):start.index("$script:Mode -eq 'Restart'")]
        self.assertIn("if ($handle -ne [IntPtr]::Zero)", start_mode)
        self.assertIn("postojeca instanca nije restartovana", start_mode)
        self.assertIn("Restart-TopElevenForStageRetry 'Discord start'", start_mode)

    def test_wake_taps_are_fail_closed_on_a_fresh_ai_frame(self):
        gate = function_body("Test-AdWakeTapAllowed")
        self.assertIn("-ForceRefresh", gate)
        self.assertIn("$script:AiTopElevenReturned", gate)
        self.assertIn("$controlReady", gate)
        self.assertIn("$script:AiAdVisible", gate)
        self.assertEqual(3, SCRIPT.count("Test-AdWakeTapAllowed $"))

    def test_return_stability_uses_fresh_frames_at_least_300ms_apart(self):
        probe = function_body("Test-TopElevenReturnedAfterAd")
        self.assertIn("[switch]$ForceRefresh", probe)
        self.assertIn("Wait-Agent 300", probe)
        followup = function_body("Wait-ForAdExitOrControl")
        self.assertIn("-ForceRefresh", followup)
        self.assertIn("Wait-Agent 300", followup)
        tv = function_body("Watch-TVAdvertisement")
        self.assertIn("Test-TopElevenReturnedAfterAd $Handle $adStartedAt -ForceRefresh", tv)

    def test_green_click_is_fresh_and_launch_must_be_observed(self):
        start = function_body("Start-Automation")
        green = start[start.index("Invoke-StageWithRecovery 'Uzmi 25 zelenih'"):]
        self.assertIn("$freshFree = Get-TeamRestFreeButtonSnapshot $handle", green)
        self.assertIn("$freshMatches", green)
        self.assertIn("Wait-TeamRestAdLaunchEvidence $handle $adStartedAt '25 zelenih'", green)
        self.assertIn("if (-not [bool]$launchEvidence.Observed)", green)
        self.assertIn("$script:FreeButtonStableCount = 0", green)

    def test_green_launch_confirmation_never_blocks_on_gemini(self):
        launch = function_body("Wait-TeamRestAdLaunchEvidence")
        self.assertNotIn("Test-AiOnlyAdControlReady", launch)
        self.assertNotIn("Invoke-VisionAnalysis", launch)
        self.assertIn("$missingStableCount -ge 2", launch)
        self.assertIn("$missingStableMilliseconds -ge 350", launch)
        self.assertIn("Observed = $true", launch)

    def test_named_mutex_guards_each_automation_run(self):
        enter = function_body("Enter-AgentInstanceMutex")
        self.assertIn("Global\\TopElevenAiAgent_", enter)
        self.assertIn("Local\\TopElevenAiAgent_", enter)
        start = function_body("Start-Automation")
        self.assertIn("Enter-AgentInstanceMutex", start)
        self.assertIn("Exit-AgentInstanceMutex", start)

    def test_python_runtime_is_portable_and_attempt_messages_are_truthful(self):
        resolver = function_body("Resolve-PythonRuntime")
        self.assertIn(".venv\\Scripts\\python.exe", resolver)
        self.assertIn("Get-Command python.exe", resolver)
        self.assertIn(".cache\\codex-runtimes", resolver)
        self.assertIn("$($stageResult.Attempts) pokusaja", SCRIPT)
        self.assertNotIn("nakon $script:StageRetryAttempts pokusaja", SCRIPT)


if __name__ == "__main__":
    unittest.main()
