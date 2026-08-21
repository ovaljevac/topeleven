import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "TopElevenAgent.ps1"
MANAGER_PATH = ROOT / "TopElevenManager.ps1"
MANAGER_LAUNCHER_PATH = ROOT / "Pokreni Top Eleven Manager.cmd"
CONFIG_PATH = ROOT / "config.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def function_body(source: str, name: str) -> str:
    """Return one PowerShell function body using brace balancing.

    Existing tests mostly slice between neighbouring functions.  Brace balancing
    keeps this regression test independent of function order while still making
    failures point at the relevant recovery contract.
    """

    match = re.search(rf"(?im)^function\s+{re.escape(name)}\s*\{{", source)
    if not match:
        raise AssertionError(f"PowerShell function {name!r} was not found")

    opening = source.find("{", match.start())
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
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
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"PowerShell function {name!r} has no closing brace")


class CentralManagerContractTests(unittest.TestCase):
    def test_manager_and_launcher_exist(self):
        self.assertTrue(
            MANAGER_PATH.is_file(),
            "Central manager must live at AI-Agent/TopElevenManager.ps1",
        )
        self.assertTrue(
            MANAGER_LAUNCHER_PATH.is_file(),
            "A double-clickable central-manager launcher is required",
        )
        launcher = read_text(MANAGER_LAUNCHER_PATH)
        self.assertIn("TopElevenManager.ps1", launcher)

    def test_manager_maps_every_supported_script_to_the_agent_mode(self):
        manager = read_text(MANAGER_PATH)
        expected_modes = (
            "Mourinho",
            "TV",
            "PutSaveza",
            "Kampus",
            "Zeleni",
            "OdmoriEkipu",
            "TreningIgraca",
            "Sve",
        )
        for mode in expected_modes:
            with self.subTest(mode=mode):
                self.assertRegex(
                    manager,
                    rf"(?i)\bMode\s*=\s*['\"]{re.escape(mode)}['\"]",
                    f"Manager launch map is missing mode {mode}",
                )

        self.assertIn("TopElevenAgent.ps1", manager)
        self.assertRegex(manager, r"(?i)Start-Process")
        self.assertIn("-Mode", manager)

    def test_manager_forwards_mode_specific_start_choices(self):
        manager = read_text(MANAGER_PATH)
        self.assertIn("-TeamRestStart", manager)
        self.assertIn("-CombinedStartStage", manager)
        self.assertIn("-AutoStart", manager)
        self.assertIn("-ExitAfterRun", manager)
        self.assertIn("-LogPath", manager)
        self.assertIn("-StopSignalPath", manager)
        for stage in ("Mourinho", "TV", "PutSaveza", "Kampus", "Zeleni"):
            with self.subTest(stage=stage):
                self.assertIn(stage, manager)

        agent = read_text(AGENT_PATH)
        param_block = agent[: agent.index("$ErrorActionPreference")]
        self.assertIn("$AutoStart", param_block)
        self.assertIn("$LogPath", param_block)
        self.assertIn("$StopSignalPath", param_block)


class CombinedStartStageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = read_text(AGENT_PATH)

    def test_cli_accepts_and_stores_combined_start_stage(self):
        param_block = self.agent[: self.agent.index("$ErrorActionPreference")]
        self.assertIn("$CombinedStartStage", param_block)
        for stage in ("Mourinho", "TV", "PutSaveza", "Kampus", "Zeleni"):
            with self.subTest(stage=stage):
                self.assertIn(f"'{stage}'", param_block)
        self.assertIn("$script:CombinedStartStage", self.agent)

    def test_combined_pipeline_keeps_order_and_skips_preceding_stages(self):
        # A data-driven stage list plus a selected start index is less error-prone
        # than five unrelated if-statements and guarantees that the selected
        # phase itself is still executed.
        self.assertIn("$combinedStages", self.agent)
        combined_start = self.agent.index("$combinedStages")
        combined_region = self.agent[combined_start:]
        positions = [
            combined_region.index(stage)
            for stage in ("Mourinho", "TV", "PutSaveza", "Kampus", "Zeleni")
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertRegex(combined_region, r"(?i)startIndex")
        self.assertRegex(
            combined_region,
            r"(?i)for\s*\(\s*\$stageIndex\s*=\s*\$startIndex",
        )


class StageRecoveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = read_text(AGENT_PATH)
        cls.config = json.loads(read_text(CONFIG_PATH))

    def test_retry_limit_is_exactly_three(self):
        self.assertEqual(3, self.config.get("stageRetryAttempts"))
        self.assertRegex(
            self.agent,
            r"\$script:StageRetryAttempts\s*=\s*3\b",
        )
        retry = function_body(self.agent, "Invoke-StageWithRecovery")
        self.assertIn(
            "for ($attempt = 1; $attempt -le $script:StageRetryAttempts; $attempt++)",
            retry,
        )
        self.assertRegex(retry, r"(?i)catch\s*\[System\.OperationCanceledException\]")
        self.assertRegex(
            retry,
            r"(?i)\$attempt\s+-lt\s+\$script:StageRetryAttempts",
            "BlueStacks must only restart when another attempt remains",
        )
        self.assertIn("Invoke-VerifiedStageRecovery", retry)
        verified_recovery = function_body(
            self.agent, "Invoke-VerifiedStageRecovery"
        )
        self.assertIn(
            "for ($recoveryAttempt = 1; $recoveryAttempt -le $script:StageRetryAttempts; $recoveryAttempt++)",
            verified_recovery,
        )
        self.assertIn("Restart-TopElevenForStageRetry", verified_recovery)

    def test_restart_force_stops_only_the_active_instance_and_relaunches(self):
        restart = function_body(self.agent, "Restart-TopElevenForStageRetry")
        stop_exact = function_body(
            self.agent, "Stop-ExactBlueStacksInstanceForRecovery"
        )
        self.assertIn("GetWindowThreadProcessId", stop_exact)
        self.assertIn("Get-Process -Id", stop_exact)
        self.assertIn("$player.CloseMainWindow()", stop_exact)
        self.assertIn("Stop-Process -Id $playerId -Force", stop_exact)
        self.assertNotRegex(stop_exact, r"(?i)Stop-Process\s+-Name\s+HD-Player")
        self.assertNotRegex(stop_exact, r"(?i)taskkill[^\r\n]*/IM")

        self.assertIn("Stop-ExactBlueStacksInstanceForRecovery $oldHandle", restart)
        self.assertIn("$script:TopElevenPackage = 'eu.nordeus.topeleven.android'", self.agent)
        self.assertTrue(
            "$script:TopElevenShortcut" in restart
            or "Invoke-BlueStacksAppCommand 'launchApp'" in restart,
            "Recovery must relaunch Top Eleven after stopping its exact instance",
        )
        self.assertIn("Get-BlueStacksWindow", restart)
        self.assertIn("return $handle", restart)
        self.assertRegex(restart, r"(?i)Wait-(Agent|ForCondition)")

    def test_combined_and_standalone_paths_share_the_same_recovery_wrapper(self):
        combined = function_body(self.agent, "Invoke-CombinedStage")
        self.assertIn("Invoke-StageWithRecovery", combined)
        success_gate = combined.index("if ($result.Success)")
        final_restart = combined.index("Invoke-VerifiedStageRecovery", success_gate)
        failure_return = combined.index("return $false", final_restart)
        self.assertLess(success_gate, final_restart)
        self.assertLess(final_restart, failure_return)
        self.assertIn("$script:StagePreflightRecoveryRequired = $true", combined)

        start = function_body(self.agent, "Start-Automation")
        self.assertGreaterEqual(
            start.count("Invoke-StageWithRecovery"),
            1,
            "Standalone dispatch must use the same three-attempt recovery wrapper",
        )
        for action in (
            "Run-MourinhoAutomation",
            "Run-TVAutomation",
            "Run-PutSavezaAutomation",
            "Run-CampusAutomation",
            "Run-TrainingPlayerAutomation",
            "Run-TeamRestManualQueue",
        ):
            with self.subTest(action=action):
                self.assertIn(action, start)
        self.assertIn("Invoke-StageWithRecovery 'Uzmi 25 zelenih'", start)


class PutSavezaTimeoutContractTests(unittest.TestCase):
    def test_idi_wait_timeout_is_exactly_thirty_seconds(self):
        agent = read_text(AGENT_PATH)
        config = json.loads(read_text(CONFIG_PATH))
        self.assertEqual(30, config.get("putSavezaAdButtonWaitSeconds"))
        self.assertRegex(
            agent,
            r"\$script:PutSavezaAdButtonWaitSeconds\s*=\s*30\b",
        )
        wait_body = function_body(agent, "Wait-PutSavezaAdDecision")
        self.assertIn("$script:PutSavezaAdButtonWaitSeconds", wait_body)


if __name__ == "__main__":
    unittest.main()
