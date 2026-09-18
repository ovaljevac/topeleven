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
    def test_reported_finishing_setup_is_recognized(self):
        frame = x_detector.load_image(str(ROOT / "tests" / "training-setup-finishing.png"))
        result = x_detector.detect_training_player_flow(frame)
        self.assertEqual("setup", result["state"])
        self.assertGreater(result["startButton"]["score"], .80)

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
        condition_plus = x_detector.detect_training_player_flow(self.image(6))["conditionPlus"]
        self.assertAlmostEqual(.955, condition_plus["x"], delta=.01)
        self.assertAlmostEqual(.652, condition_plus["y"], delta=.01)

    def test_full_besplatno_is_required(self):
        ready = self.image(7)
        result = x_detector.detect_training_player_flow(ready)
        self.assertTrue(result["freeButton"]["ready"])

        loading = ready.copy()
        height, width = loading.shape[:2]
        loading[int(height * .83):height, int(width * .60):int(width * .84)] = (210, 155, 65)
        result = x_detector.detect_training_player_flow(loading)
        self.assertFalse(result.get("freeButton", {}).get("ready", False))

    def test_reported_condition_offer_is_ready_and_controls_are_grounded(self):
        original = x_detector.load_image(str(ROOT / "tests" / "training-condition-ready.png"))
        for size in ((1049, 605), (1280, 720)):
            with self.subTest(size=size):
                frame = x_detector.cv2.resize(original, size)
                result = x_detector.detect_training_player_flow(frame)
                self.assertEqual("condition_modal", result["state"])
                self.assertTrue(result["freeButton"]["ready"])
                self.assertAlmostEqual(.671, result["freeButton"]["x"], delta=.005)
                self.assertAlmostEqual(.569, result["modalClose"]["x"], delta=.005)
                self.assertAlmostEqual(.871, result["modalClose"]["y"], delta=.005)

    def test_reported_modal_does_not_make_loading_or_grey_offer_ready(self):
        original = x_detector.load_image(str(ROOT / "tests" / "training-condition-ready.png"))
        for color in ((210, 155, 65), (130, 130, 130)):
            with self.subTest(color=color):
                frame = original.copy()
                frame[500:554, 633:773] = color
                result = x_detector.detect_training_player_flow(frame)
                self.assertEqual("condition_modal", result["state"])
                self.assertFalse(result["freeButton"]["ready"])

    def test_distant_modal_without_red_close_is_rejected(self):
        frame = x_detector.load_image(str(ROOT / "tests" / "training-condition-ready.png"))
        frame[500:554, 566:628] = 0
        self.assertEqual("unknown", x_detector.detect_training_player_flow(frame)["state"])

    def test_reported_player_profile_survives_reference_appearance_changes(self):
        frame = x_detector.load_image(str(ROOT / "bluestacks-error.png"))
        for size in ((1049, 605), (1280, 720)):
            with self.subTest(size=size):
                scaled = x_detector.cv2.resize(frame, size)
                result = x_detector.detect_training_player_flow(scaled)
                self.assertEqual("player_detail", result["state"])
                self.assertTrue(result["profileVerified"])
                self.assertGreater(result["distance"], 35)
                self.assertAlmostEqual(.862, result["conditionPlus"]["x"], delta=.01)
                self.assertAlmostEqual(.673, result["conditionPlus"]["y"], delta=.01)
                self.assertNotIn("condition", result)

    def test_distant_profile_requires_all_three_column_markers(self):
        original = x_detector.load_image(str(ROOT / "bluestacks-error.png"))
        h, w = original.shape[:2]
        for left, right in ((.22, .36), (.42, .58), (.64, .80)):
            with self.subTest(column=left):
                frame = original.copy()
                frame[int(h * .48):int(h * .72), int(w * left):int(w * right)] = 180
                result = x_detector.detect_training_player_flow(frame)
                self.assertEqual("unknown", result["state"])

    def test_local_detector_does_not_decide_condition_from_bar_color(self):
        result = x_detector.detect_training_player_flow(self.image(4))
        self.assertNotIn("lowConditionPlayer", result)
        self.assertNotIn("lowestCondition", result)
        detail = x_detector.detect_training_player_flow(self.image(6))
        self.assertNotIn("condition", detail)
        self.assertNotIn("playerClose", detail)
        self.assertTrue(detail["profileVerified"])
        self.assertGreater(detail["profileSignature"]["lightModalRatio"], 0.58)

    def test_mode_launcher_and_ad_return_are_integrated(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'TreningIgraca'", script)
        self.assertIn("Run-TrainingPlayerAutomation $stageHandle", script)
        self.assertIn("Invoke-StageWithRecovery 'Trening igraca'", script)
        self.assertIn("'training_player'", script)
        launcher = ROOT / "Trening igraca" / "Pokreni Trening igraca Agent.cmd"
        self.assertTrue(launcher.is_file())
        self.assertIn("-Mode TreningIgraca", launcher.read_text(encoding="utf-8"))

    def test_training_phase_start_can_use_two_local_frames_without_gemini(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        helper_start = script.index("function Test-TrainingPlayerPhaseStartReady")
        helper_end = script.index("function Wait-TrainingPlayerState", helper_start)
        helper = script[helper_start:helper_end]
        self.assertEqual(2, helper.count("Get-TrainingPlayerFlowSnapshot $Handle"))
        self.assertIn("@('home', 'training_home')", helper)
        self.assertNotIn("com.android.vending", helper)
        self.assertNotIn("com.android.chrome", helper)
        self.assertNotIn("*AdActivity*", helper)
        self.assertNotIn("Invoke-VisionAnalysis", helper)
        self.assertNotIn("Test-Ai", helper)

        stage_start = script.index("function Invoke-StageWithRecovery")
        stage_end = script.index("function Invoke-CombinedStage", stage_start)
        stage = script[stage_start:stage_end]
        local_gate = stage.index("Test-TrainingPlayerPhaseStartReady")
        generic_gate = stage.index("Restore-ExternalNavigationBeforeGameAction", local_gate)
        self.assertLess(local_gate, generic_gate)

    def test_training_does_not_reopen_menu_when_training_home_is_already_open(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        already_open = flow.index("$initialTrainingState.state -eq 'training_home'")
        menu_click = flow.index("'bocni meni - Trening igraca'", already_open)
        self.assertLess(already_open, menu_click)

    def test_backup_api_key_switch_is_logged_only_when_slot_changes(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("$script:LastLoggedGeminiKeySlot = 1", script)
        invoke_start = script.index("function Invoke-VisionAnalysis")
        invoke_end = script.index("function Test-AiOnlyAdControlReady", invoke_start)
        invoke = script[invoke_start:invoke_end]
        self.assertIn("$usedKeySlot -ne $script:LastLoggedGeminiKeySlot", invoke)
        self.assertIn("$script:LastLoggedGeminiKeySlot = $usedKeySlot", invoke)

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
        result_wait = flow.index("@('training_result', 'exhausted_players')", neutral_touch)
        self.assertLess(start_click, one_second)
        self.assertLess(one_second, neutral_touch)
        self.assertLess(neutral_touch, result_wait)
        self.assertIn("Click-TrainingPlayerClose $Handle", flow)

    def test_exhausted_player_row_opens_without_setup_ai(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        start = script.index("function Run-TrainingPlayerAutomation")
        end = script.index("function Get-CampusFlowSnapshot", start)
        flow = script[start:end]
        training_click = flow.index("'ZAPOCNI TRENING'")
        close = flow.index("'X - UMORNI IGRACI'", training_click)
        player_click = flow.index("'umorni igrac - jedini red na setup ekranu'", close)
        self.assertLess(training_click, close)
        self.assertLess(close, player_click)
        self.assertNotIn("Get-AiTrainingSetupCondition $Handle", flow)
        self.assertIn("Click-TrainingPlayerRelative $Handle 0.500 0.575", flow)
        self.assertIn("$result = $afterStart", flow[training_click:close])

    def test_exhaustion_dialog_requires_title_and_close(self):
        original = x_detector.load_image(str(ROOT / "Trening igraca" / "exhausted.png"))
        for size in ((1049, 605), (1280, 720)):
            frame = x_detector.cv2.resize(original, size)
            result = x_detector.detect_training_player_flow(frame)
            self.assertEqual("exhausted_players", result["state"])
            self.assertAlmostEqual(.830, result["closeButton"]["x"], delta=.01)
            self.assertNotIn("freeButton", result)
        for rect in ((.10, .27, .28, .33), (.80, .26, .86, .34)):
            frame = original.copy()
            h, w = frame.shape[:2]
            l, t, r, b = rect
            frame[int(t*h):int(b*h), int(l*w):int(r*w)] = 0
            self.assertNotEqual("exhausted_players", x_detector.detect_training_player_flow(frame)["state"])

    def test_training_percentages_are_ai_only(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("function Get-AiTrainingSetupCondition", script)
        self.assertIn("function Get-AiTrainingProfileCondition", script)
        self.assertNotIn("lowConditionPlayer", script)
        self.assertIn("$detail.conditionPlus", script)
        self.assertNotIn("$detail.playerClose", script)
        self.assertIn("if ($condition -ge 85)", script)
        detector = (ROOT / "XDetector.py").read_text(encoding="utf-8")
        self.assertNotIn("_condition_from_bar", detector)

    def test_profile_condition_is_checked_only_after_four_recoveries(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        start = script.index("function Restore-TrainingPlayerCondition")
        end = script.index("function Run-TrainingPlayerAutomation", start)
        restore = script[start:end]
        mandatory_loop = restore.index("for ($reward = 1; $reward -le 4; $reward++)")
        ai_check = restore.index("Get-AiTrainingProfileCondition $Handle")
        self.assertLess(mandatory_loop, ai_check)
        self.assertEqual(1, restore.count("Get-AiTrainingProfileCondition $Handle"))
        self.assertIn("if ($condition -ge 85)", restore[ai_check:])
        self.assertIn("zeleni + za peti oporavak kondicije - AI", restore[ai_check:])
        self.assertIn("Send-Escape $Handle", restore[ai_check:])

    def test_one_ai_close_is_enough_only_with_fresh_local_verification(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        guard_start = script.index("function Confirm-AiAdCloseImmediatelyBeforeClick")
        guard_end = script.index("function Test-AdWakeTapAllowed", guard_start)
        guard = script[guard_start:guard_end]
        self.assertNotIn("Test-AiOnlyAdControlReady", guard)
        self.assertNotIn("Invoke-VisionAnalysis", guard)
        self.assertIn("$script:DetectedAdCloseLocallyVerified", guard)
        self.assertIn("Jedna AI provjera", guard)
        self.assertIn("return 'close'", guard)
        self.assertIn("return 'not_confirmed'", guard)
        ai_check_start = script.index("function Test-AiOnlyAdControlReady")
        ai_check_end = guard_start
        ai_check = script[ai_check_start:ai_check_end]
        self.assertGreaterEqual(ai_check.count("$script:DetectedAdCloseX = $null"), 2)
        fallback_start = ai_check.index("fallbackToAiCoordinate")
        fallback = ai_check[fallback_start:]
        self.assertIn("kandidat je odbijen", fallback)
        self.assertIn("$script:DetectedAdCloseLocallyVerified = $false", fallback)
        self.assertIn("return $false", fallback)
        self.assertIn("Confirm-AiAdCloseImmediatelyBeforeClick $Handle \"$flowLabel reklama\"", script)
        self.assertIn("Confirm-AiAdCloseImmediatelyBeforeClick $Handle \"Reklama za $PlayerLabel\"", script)
        self.assertIn("Confirm-AiAdCloseImmediatelyBeforeClick $handle 'Reklama'", script)

    def test_training_player_return_accepts_two_stable_profile_frames(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        watch_start = script.index("function Watch-TVAdvertisement")
        watch_end = script.index("function Complete-TVManualReward", watch_start)
        watch = script[watch_start:watch_end]
        local_return = watch[watch.index("$trainingPlayerReturnStableCount = 0"):]
        self.assertIn("$ReturnFlow -eq 'training_player'", local_return)
        self.assertIn("$adObserved", local_return)
        self.assertIn("$aiAdVisuallyObserved", local_return)
        self.assertIn("Get-TrainingPlayerFlowSnapshot $Handle", local_return)
        self.assertIn("$trainingReturn.state -eq 'player_detail'", local_return)
        self.assertIn("$trainingReturn.profileVerified", local_return)
        self.assertNotIn("$trainingHeaderReady", local_return)
        self.assertIn("$trainingPlayerReturnStableCount -ge 2", local_return)
        self.assertIn("return 'top_eleven'", local_return)
        self.assertLess(
            local_return.index("Get-TrainingPlayerFlowSnapshot $Handle"),
            local_return.index("Test-TopElevenReturnedAfterAd $Handle"),
        )

    def test_tv_manual_reward_accepts_two_stable_manual_frames_before_android_main_gate(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        watch_start = script.index("function Watch-TVAdvertisement")
        watch_end = script.index("function Complete-TVManualReward", watch_start)
        watch = script[watch_start:watch_end]
        local_return = watch[watch.index("$tvManualReturnStableCount = 0"):]
        self.assertIn("$ReturnFlow -eq 'tv'", local_return)
        self.assertIn("$ManualReward", local_return)
        self.assertIn("$adObserved", local_return)
        self.assertIn("$aiAdVisuallyObserved", local_return)
        self.assertIn("Get-TVFlowSnapshot $Handle", local_return)
        self.assertIn("$manualReturn.state -eq 'manual_3'", local_return)
        self.assertIn("$tvManualReturnStableCount -ge 2", local_return)
        self.assertIn("return 'manual_3'", local_return)
        self.assertLess(
            local_return.index("$manualReturn = Get-TVFlowSnapshot $Handle"),
            local_return.index("Test-TopElevenReturnedAfterAd $Handle"),
        )

    def test_regular_tv_reward_accepts_two_tv_frames_but_manual_reward_does_not(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        watch_start = script.index("function Watch-TVAdvertisement")
        watch_end = script.index("function Complete-TVManualReward", watch_start)
        watch = script[watch_start:watch_end]
        local_return = watch[watch.index("$tvReturnStableCount = 0"):]
        self.assertIn("$ReturnFlow -eq 'tv'", local_return)
        self.assertIn("-not $ManualReward", local_return)
        self.assertIn("$adObserved", local_return)
        self.assertIn("$aiAdVisuallyObserved", local_return)
        self.assertIn("$tvReturn = Get-TVFlowSnapshot $Handle", local_return)
        self.assertIn("$tvReturn.state -eq 'tv'", local_return)
        self.assertIn("$tvReturnStableCount -ge 2", local_return)
        self.assertIn("return 'tv'", local_return)
        self.assertLess(
            local_return.index("$tvReturn = Get-TVFlowSnapshot $Handle"),
            local_return.index("Test-TopElevenReturnedAfterAd $Handle"),
        )

    def test_local_ad_return_requires_sticky_ai_proof_that_ad_was_visually_seen(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        watch_start = script.index("function Watch-TVAdvertisement")
        watch_end = script.index("function Complete-TVManualReward", watch_start)
        watch = script[watch_start:watch_end]
        self.assertIn("$aiAdVisuallyObserved = $false", watch)
        sticky_set = watch.index("$aiAdVisuallyObserved = $true")
        ai_visible = watch.rindex("if ($script:AiAdVisible)", 0, sticky_set)
        self.assertLess(ai_visible, sticky_set)
        # All five local return paths accept a confirmed external departure,
        # but still require their own verified return screen.
        self.assertEqual(5, watch.count("($aiAdVisuallyObserved -or $externalDepartureObserved) -and"))

    def test_confirmed_training_profile_is_not_blocked_by_second_main_activity_gate(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        restore_start = script.index("function Restore-TrainingPlayerCondition")
        restore_end = script.index("function Run-TrainingPlayerAutomation", restore_start)
        restore = script[restore_start:restore_end]
        ad_exit = restore[restore.index("Watch-TVAdvertisement $Handle $false 'training_player'"):]
        self.assertIn("$trainingAdExit -ne 'top_eleven'", ad_exit)
        self.assertNotIn("Restore-ExternalNavigationBeforeGameAction", ad_exit)

    def test_ad_ai_probe_starts_and_repeats_at_twelve_seconds(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        config = (ROOT / "ai_config.json").read_text(encoding="utf-8")
        self.assertIn("$script:VisionAiProbeIntervalSeconds = 12.0", script)
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
        self.assertIn('"aiProbeIntervalSeconds": 12.0', config)

    def test_rejected_preclick_uses_probe_cooldown_instead_of_one_second_loop(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        helper_start = script.index("function Get-AiPreClickRetryIntervalSeconds")
        helper_end = script.index("function Stop-AgentProcessAfterIoFailure", helper_start)
        helper = script[helper_start:helper_end]
        self.assertIn("[Math]::Max(4.1", helper)
        self.assertIn("$script:VisionAiProbeIntervalSeconds", helper)

        manual_start = script.index("$adClosed = $false", script.index("function Wait-ManualTeamRestAd"))
        manual_end = script.index("function Run-TeamRestManualQueue", manual_start)
        manual_close = script[manual_start:manual_end]
        self.assertIn("Get-AiPreClickRetryIntervalSeconds", manual_close)
        manual_rejection_start = manual_close.index("if ($preClickState -ne 'close')")
        manual_rejection = manual_close[
            manual_rejection_start:
            manual_close.index("continue", manual_rejection_start) + len("continue")
        ]
        self.assertNotIn("Wait-Agent 1000", manual_rejection)

        green_start = script.index(
            "$adClosed = $adAlreadyExited", script.index("function Start-Automation")
        )
        green_end = script.index("if ($adClosed)", green_start)
        green_close = script[green_start:green_end]
        self.assertIn("Get-AiPreClickRetryIntervalSeconds", green_close)
        green_rejection_start = green_close.index("if ($preClickState -ne 'close')")
        green_rejection = green_close[
            green_rejection_start:
            green_close.index("continue", green_rejection_start) + len("continue")
        ]
        self.assertNotIn("Wait-Agent 1000", green_rejection)

        tv_start = script.index("function Watch-TVAdvertisement")
        tv_end = script.index("function Complete-TVManualReward", tv_start)
        tv = script[tv_start:tv_end]
        self.assertIn("$nextPreClickAiAllowedAt = [datetime]::MinValue", tv)
        self.assertIn("(Get-Date) -ge $nextPreClickAiAllowedAt", tv)
        self.assertIn("$nextAiProbeAt = $nextPreClickAiAllowedAt", tv)
        rejection_start = tv.index("if ($preClickState -ne 'close')")
        rejection = tv[rejection_start:tv.index("continue", rejection_start) + len("continue")]
        self.assertNotIn("$nextAiProbeAt = Get-Date", rejection)

    def test_google_play_restore_does_not_require_a_recent_badge_click(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        restore_start = script.index("function Restore-AdFromGooglePlay")
        restore_end = script.index("function Wait-ForAdXAfterGooglePlayReturn", restore_start)
        restore = script[restore_start:restore_end]
        self.assertIn("Test-AiExternalNavigationVisible $Handle $AdStartedAt", restore)
        self.assertNotIn("$recentAiPlayClick", restore)
        self.assertNotIn("TotalSeconds -le 15", restore)

    def test_stage_recovery_keeps_one_ai_stability_key(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        recovery_start = script.index("function Restart-TopElevenForStageRetry")
        recovery_end = script.index("function Invoke-VerifiedStageRecovery", recovery_start)
        recovery = script[recovery_start:recovery_end]
        assignment = '$recoveryState = "stage_recovery_top_eleven_ai_only_$($launchedAt.Ticks)"'
        self.assertEqual(1, recovery.count(assignment))
        loop_start = recovery.index("while ((Get-Date) -lt $deadline)")
        self.assertNotIn("stage_recovery_top_eleven_ai_only_$((Get-Date).Ticks)", recovery[loop_start:])

    def test_soft_ai_retries_keep_one_state_key_so_one_of_two_can_advance(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        function_pairs = (
            ("Get-AiTrainingSetupCondition", "Get-AiTrainingProfileCondition"),
            ("Get-AiTrainingProfileCondition", "Restore-TrainingPlayerCondition"),
            ("Get-AiCampusToolButton", "Resolve-AiCampusBuilding"),
            ("Resolve-AiCampusBuilding", "Wait-CampusDetailOpened"),
        )
        for function_name, next_function in function_pairs:
            with self.subTest(function=function_name):
                start = script.index(f"function {function_name}")
                end = script.index(f"function {next_function}", start)
                body = script[start:end]
                loop_start = body.index("while ((Get-Date) -lt $deadline)")
                self.assertIn("$script:VisionCacheByState.Remove(", body[:loop_start])
                self.assertNotIn("$((Get-Date).Ticks)", body[loop_start:])
                self.assertNotIn("_soft_$attempt", body[loop_start:])

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
            "lokalni verifier nije nasao X blizu te tacke",
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
        self.assertIn(
            "$deadline = (Get-Date).AddSeconds($script:AiSoftRetryTimeoutSeconds)",
            setup,
        )
        self.assertIn("while ((Get-Date) -lt $deadline)", setup)
        self.assertIn(
            "Wait-Agent ($script:AiSoftRetryIntervalSeconds * 1000)", setup
        )
        self.assertNotIn("Get-AiTrainingSetupCondition $Handle (", setup)
        self.assertIn("Try-RecoverConnectionInterruptedPopup $Handle", profile)
        self.assertIn(
            "$deadline = (Get-Date).AddSeconds($script:AiSoftRetryTimeoutSeconds)",
            profile,
        )
        self.assertIn("while ((Get-Date) -lt $deadline)", profile)
        self.assertIn(
            "Wait-Agent ($script:AiSoftRetryIntervalSeconds * 1000)", profile
        )
        self.assertNotIn("Get-AiTrainingProfileCondition $Handle (", profile)


if __name__ == "__main__":
    unittest.main()
