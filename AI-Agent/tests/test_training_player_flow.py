import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pydeps"))
SPEC = importlib.util.spec_from_file_location("x_detector_training", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


class TrainingPlayerFlowTests(unittest.TestCase):
    def image(self, index):
        return x_detector.load_image(str(ROOT / "Trening igraca" / f"{index}.png"))

    def test_reference_flow_states_and_controls(self):
        expected = {
            1: "home", 2: "training_home", 3: "reports", 4: "setup",
            5: "training_result", 6: "player_detail",
            7: "condition_modal", 8: "training_home",
        }
        for index, state in expected.items():
            with self.subTest(index=index):
                self.assertEqual(state, x_detector.detect_training_player_flow(self.image(index))["state"])
        self.assertIsNotNone(x_detector.detect_training_player_flow(self.image(2))["reportsButton"])
        self.assertIsNotNone(x_detector.detect_training_player_flow(self.image(3))["repeatButton"])
        self.assertIsNotNone(x_detector.detect_training_player_flow(self.image(4))["startButton"])
        self.assertIsNotNone(x_detector.detect_training_player_flow(self.image(5))["closeButton"])
        self.assertNotIn("conditionPlus", x_detector.detect_training_player_flow(self.image(6)))

    def test_full_besplatno_is_required(self):
        ready = self.image(7)
        result = x_detector.detect_training_player_flow(ready)
        self.assertTrue(result["freeButton"]["ready"])

        loading = ready.copy()
        height, width = loading.shape[:2]
        loading[int(height * .83):height, int(width * .60):int(width * .84)] = (210, 155, 65)
        result = x_detector.detect_training_player_flow(loading)
        self.assertFalse(result.get("freeButton", {}).get("ready", False))

    def test_local_detector_does_not_decide_condition_from_bar_color(self):
        result = x_detector.detect_training_player_flow(self.image(4))
        self.assertNotIn("lowConditionPlayer", result)
        self.assertNotIn("lowestCondition", result)
        detail = x_detector.detect_training_player_flow(self.image(6))
        self.assertNotIn("condition", detail)
        self.assertNotIn("playerClose", detail)

    def test_mode_launcher_and_ad_return_are_integrated(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'TreningIgraca'", script)
        self.assertIn("Run-TrainingPlayerAutomation $stageHandle", script)
        self.assertIn("Invoke-StageWithRecovery 'Trening igraca'", script)
        self.assertIn("'training_player'", script)
        launcher = ROOT / "Trening igraca" / "Pokreni Trening igraca Agent.cmd"
        self.assertTrue(launcher.is_file())
        self.assertIn("-Mode TreningIgraca", launcher.read_text(encoding="utf-8"))

    def test_training_flow_does_not_overwrite_powershell_home_constant(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        self.assertNotIn("$home =", flow.lower())
        self.assertIn("$trainingHomeSnapshot", flow)

    def test_every_training_click_uses_the_configured_buffer(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$script:TrainingPlayerClickBufferMs = 1800", script)
        self.assertIn("Wait-Agent $script:TrainingPlayerClickBufferMs", script)
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        self.assertEqual(1, flow.count("Click-Relative $Handle"))
        self.assertNotIn("Click-GameRelative $Handle", flow)

    def test_training_taps_after_one_second_and_delays_close_buttons(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$script:TrainingPlayerCloseBufferMs = 1500", script)
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        start_click = flow.index("'ZAPOCNI TRENING'")
        one_second = flow.index("Wait-Agent 1000", start_click)
        neutral_touch = flow.index("'Trening - jedan dodir nakon 1 sekunde'", one_second)
        result_wait = flow.index("@('training_result')", neutral_touch)
        self.assertLess(start_click, one_second)
        self.assertLess(one_second, neutral_touch)
        self.assertLess(neutral_touch, result_wait)
        self.assertIn("Click-TrainingPlayerClose $Handle", flow)

    def test_start_training_has_fresh_low_condition_safety_gate(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        fresh_gate = flow.index("$freshConditionDecision = Get-AiTrainingSetupCondition $Handle")
        blocked = flow.index("Sigurnosna blokada: AI jos vidi igraca", fresh_gate)
        training_click = flow.index("'ZAPOCNI TRENING'", blocked)
        self.assertLess(fresh_gate, blocked)
        self.assertLess(blocked, training_click)

    def test_training_percentages_are_ai_only(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("function Get-AiTrainingSetupCondition", script)
        self.assertIn("function Get-AiTrainingProfileCondition", script)
        self.assertNotIn("lowConditionPlayer", script)
        self.assertNotIn("$detail.conditionPlus", script)
        self.assertNotIn("$detail.playerClose", script)
        self.assertIn("if ($condition -ge 85)", script)
        detector = (ROOT / "XDetector.py").read_text(encoding="utf-8")
        self.assertNotIn("_condition_from_bar", detector)

    def test_ad_close_coordinates_are_cleared_and_rechecked_before_click(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        guard_start = script.index("function Confirm-AiAdCloseImmediatelyBeforeClick")
        guard_end = script.index("function Test-AiExternalNavigationVisible", guard_start)
        guard = script[guard_start:guard_end]
        self.assertIn("Test-AiOnlyAdControlReady", guard)
        self.assertIn("se vec sama zatvorila", guard)
        ai_check_start = script.index("function Test-AiOnlyAdControlReady")
        ai_check_end = guard_start
        ai_check = script[ai_check_start:ai_check_end]
        self.assertGreaterEqual(ai_check.count("$script:DetectedAdCloseX = $null"), 2)
        self.assertIn("Confirm-AiAdCloseImmediatelyBeforeClick $Handle \"$flowLabel reklama\"", script)
        self.assertIn("Confirm-AiAdCloseImmediatelyBeforeClick $Handle \"Reklama za $PlayerLabel\"", script)

    def test_ad_ai_probe_starts_and_repeats_at_twenty_point_five_seconds(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        config = (ROOT / "ai_config.json").read_text(encoding="utf-8")
        self.assertIn("$script:VisionAiProbeIntervalSeconds = 20.5", script)
        self.assertIn("[double]$visionConfig.aiProbeIntervalSeconds", script)
        self.assertNotIn(
            "$nextAiProbeAt = $adStartedAt.AddSeconds($script:XDetectionDelaySeconds)",
            script,
        )
        self.assertGreaterEqual(
            script.count(
                "$nextAiProbeAt = $adStartedAt.AddSeconds($script:VisionAiProbeIntervalSeconds)"
            ),
            3,
        )
        self.assertIn('"aiProbeIntervalSeconds": 20.5', config)

    def test_unstable_preclick_check_resumes_automatic_monitoring(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("reklama mozda nije zatvorena - provjerite", script)
        self.assertNotIn("rucna intervencija", script)
        self.assertGreaterEqual(
            script.count("while ((Get-Date) -lt $adCloseDeadline -and -not $adClosed)"),
            2,
        )
        self.assertIn(
            "nastavljam automatski nadzor umjesto prekida",
            script,
        )
        self.assertIn(
            "cekam novu svjezu AI potvrdu X-a ili povratka",
            script,
        )
        self.assertIn(
            "lokalni verifier ne poznaje ovaj stil X-a pa koristim tacan AI centar bez pomaka",
            script,
        )

    def test_connection_interrupted_popup_is_recovered_in_all_state_waiters(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        config = (ROOT / "config.json").read_text(encoding="utf-8")
        self.assertIn("function Try-RecoverConnectionInterruptedPopup", script)
        self.assertIn("click_connection_confirm", script)
        self.assertIn("VEZA JE PREKINUTA - potvrda AI", script)
        self.assertIn("$script:ConnectionRecoveryWaitMs = 12000", script)
        self.assertIn('"connectionRecoveryWaitMs": 12000', config)
        self.assertGreaterEqual(
            script.count("if (Try-RecoverConnectionInterruptedPopup $Handle)"),
            5,
        )
        self.assertGreaterEqual(
            script.count("$deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSeconds, 45))"),
            5,
        )

    def test_incidental_popup_is_closed_and_training_ai_retries(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        recovery_start = script.index("function Try-RecoverConnectionInterruptedPopup")
        recovery_end = script.index("function Test-AiExternalNavigationVisible", recovery_start)
        recovery = script[recovery_start:recovery_end]
        self.assertIn("incidental_top_eleven_popup_", recovery)
        self.assertIn("click_incidental_popup_close", recovery)
        self.assertIn("Neocekivani Top Eleven popup - AI X", recovery)
        setup_start = script.index("function Get-AiTrainingSetupCondition")
        profile_start = script.index("function Get-AiTrainingProfileCondition", setup_start)
        setup = script[setup_start:profile_start]
        profile_end = script.index("function Restore-TrainingPlayerCondition", profile_start)
        profile = script[profile_start:profile_end]
        self.assertIn("Try-RecoverConnectionInterruptedPopup $Handle", setup)
        self.assertIn("Get-AiTrainingSetupCondition $Handle ($RecoveryAttempt + 1)", setup)
        self.assertIn("Try-RecoverConnectionInterruptedPopup $Handle", profile)
        self.assertIn("Get-AiTrainingProfileCondition $Handle ($RecoveryAttempt + 1)", profile)


if __name__ == "__main__":
    unittest.main()
