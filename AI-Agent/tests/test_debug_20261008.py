"""Offline regression against the debug frames supplied on 8 October 2026."""
import json
import io
import unittest
from unittest.mock import patch
from pathlib import Path

from test_vision_agent import vision_agent as vision
from test_external_navigation_recovery import function_source, run_powershell

ROOT = Path(__file__).resolve().parents[1]
DEBUG = ROOT / "debug"
CONFIG = {"minimumConfidence": .85}


class SuppliedDebugFrameTests(unittest.TestCase):
    def records(self, pattern):
        paths = sorted(DEBUG.glob(pattern))
        if not paths:
            self.skipTest("optional supplied debug frames are absent")
        for path in paths:
            frame = path.with_suffix(".jpg")
            if frame.exists():
                yield path, json.loads(path.read_text(encoding="utf-8-sig")), frame

    def test_real_ad_exits_are_not_blocked_by_install_elsewhere(self):
        for path, record, frame in self.records("20261008-1[12]*-rejected.json"):
            raw = record["decision"]
            if raw["recommendedAction"] not in {"click_close", "click_skip", "click_google_play"}:
                continue
            with self.subTest(frame=path.name), vision.Image.open(frame) as image:
                normalized, errors = vision.validate_decision(raw, CONFIG, "ad_control_ai_only_fixture", image.size)
                self.assertEqual([], errors)
                # Legacy ad_control checks also must ignore unrelated Install text.
                _, errors = vision.validate_decision(raw, CONFIG, "ad_control", image.size)
                self.assertEqual([], errors)
                if raw["recommendedAction"] == "click_google_play":
                    _, evidence = vision.refine_decision_control_center(image, normalized)
                    self.assertIsNotNone(evidence)
                elif raw["recommendedAction"] == "click_close":
                    _, evidence = vision.refine_ai_close_on_fresh_frame(image, normalized)
                    self.assertTrue(evidence["applied"], evidence)

    def test_campus_yellow_and_red_badges_ground_stadium_on_every_supplied_frame(self):
        for path, record, frame in self.records("20261008-112*-campus-grounding-rejected.json"):
            with self.subTest(frame=path.name), vision.Image.open(frame) as image:
                result = vision.ground_campus_click_on_fresh_frame(image, record["decision"])
                self.assertTrue(result["ok"], result)
                self.assertEqual("stadion", result["target"])
                self.assertGreaterEqual(result["maintenanceBadgeCount"], 3)
                self.assertTrue(.46 < result["x"] < .52 and .60 < result["y"] < .68)

    def test_construction_timer_cannot_be_clicked_as_maintenance(self):
        _, record, frame = next(self.records("20261008-112130-*-campus-grounding-rejected.json"))
        record["decision"]["visibleText"] = "TARGET: LABORATORIJA VEZBI; PERCENT: 60%"
        with vision.Image.open(frame) as image:
            result = vision.ground_campus_click_on_fresh_frame(image, record["decision"])
        self.assertFalse(result["ok"], result)
        self.assertIn("construction timer", result["error"])

    def test_wrong_game_actions_remain_rejected_during_connection_check(self):
        for path, record, frame in self.records("20261008-110*-rejected.json"):
            if record["decision"]["recommendedAction"] != "click_target":
                continue
            with self.subTest(frame=path.name):
                _, errors = vision.validate_decision(record["decision"], CONFIG, "connection_interrupted_popup_fixture")
                self.assertIn("click_target is only allowed for mourinho_warning", errors)

    def test_empty_unknown_frames_never_allow_portrait_wake(self):
        # Only the supplied morning frames are known to be blank. Later
        # runtime captures can be unrelated apps with substantial content.
        for path, _, frame in self.records("20261008-1[12]*-unknown.json"):
            with self.subTest(frame=path.name), vision.Image.open(frame) as image:
                self.assertFalse(vision.portrait_wake_has_content(image))

    def test_populated_portrait_can_pass_content_veto(self):
        _, _, frame = next(self.records("20261008-110448-*-rejected.json"))
        with vision.Image.open(frame) as image:
            portrait = image.resize((360, 615))
        self.assertTrue(vision.portrait_wake_has_content(portrait))

    def test_install_controls_fail_google_play_wordmark_verifier(self):
        import XDetector
        import cv2

        for path, record, frame in self.records("20261008-1[12]*-rejected.json"):
            if record["decision"]["screenType"] != "ad":
                continue
            image = cv2.imread(str(frame))
            for x, y in ((.70, .46), (.90, .90), (.50, .68)):
                with self.subTest(frame=path.name, point=(x, y)):
                    result = XDetector.verify_ai_google_play_badge(image, {"x": x, "y": y})
                    self.assertFalse(result["found"], result)


class WakeGateExecutionTests(unittest.TestCase):
    def test_blank_content_is_vetoed_even_with_emulator_chrome(self):
        for color in ("black", "#333333", "#ee4924"):
            image = vision.Image.new("RGB", (360, 615), color)
            draw = vision.ImageDraw.Draw(image)
            draw.rectangle((0, 0, 360, 32), fill="white")
            draw.rectangle((328, 32, 360, 615), fill="blue")
            draw.text((6, 595), "ad info", fill="white")
            self.assertFalse(vision.portrait_wake_has_content(image))

    def test_server_vetoes_transition_to_blank_after_ai_answers(self):
        populated = vision.Image.new("RGB", (360, 615), "black")
        draw = vision.ImageDraw.Draw(populated)
        for y in range(80, 540, 20):
            for x in range(25, 300, 20):
                draw.rectangle((x, y, x+10, y+10), fill="white")
        self.assertTrue(vision.portrait_wake_has_content(populated))
        blank = vision.Image.new("RGB", (360, 615), "black")
        result = {"ok": True, "accepted": True, "decision": {
            "screenType": "ad", "topElevenReturned": False,
            "recommendedAction": "none", "control": {"type": "none", "x": None, "y": None},
        }}
        request = {"rect": [0, 0, 360, 615], "expectedState": "ad_control_ai_only_wake_fixture"}
        with patch.object(vision, "VisionServer") as server, \
                patch.object(vision, "capture_rect", side_effect=[populated, blank, blank]), \
                patch.object(vision, "recover_strict_reward_granted_close", return_value=(result["decision"], None)), \
                patch.object(vision, "recover_strict_top_edge_skip", return_value=(result["decision"], None)), \
                patch.object(vision.sys, "stdin", io.StringIO(json.dumps(request)+"\n")), \
                patch.object(vision.sys, "stdout", io.StringIO()) as output:
            server.return_value.analyze.return_value = result
            vision.serve({"provider": "gemini", "enabled": True})
        self.assertFalse(json.loads(output.getvalue())["wakeTapAllowed"])

    def test_wake_requires_content_and_fresh_ai_ad_without_exit(self):
        command = r'''
$script:AdWakeAnalysisPerformed = $false
$script:Portrait = $true
function Get-GameViewportRectangle { return @{ Left=0; Right=300; Top=0; Bottom=$(if ($script:Portrait) {600} else {180}) } }
function Add-Log { param($Message) }
function Test-AiOnlyAdControlReady {
    param($Handle, $ExpectedState, [switch]$ForceRefresh)
    if (-not $ForceRefresh) { throw 'wake reused an old frame' }
    $script:AiAdVisible = $script:Ad
    $script:AiTopElevenReturned = $script:Returned
    $script:AiAdWakeTapAllowed = $script:Content
    return $script:Control
}
''' + function_source("Test-AdWakeTapAllowed") + r'''
$results = @()
foreach ($case in @(
    @{ad=$true; content=$false; returned=$false; control=$false; portrait=$true},
    @{ad=$true; content=$true; returned=$false; control=$false; portrait=$true},
    @{ad=$false; content=$true; returned=$false; control=$false; portrait=$true},
    @{ad=$true; content=$true; returned=$true; control=$false; portrait=$true},
    @{ad=$true; content=$true; returned=$false; control=$true; portrait=$true},
    @{ad=$true; content=$true; returned=$false; control=$false; portrait=$false}
)) {
    $script:Ad=$case.ad; $script:Content=$case.content
    $script:Returned=$case.returned; $script:Control=$case.control; $script:Portrait=$case.portrait
    $results += [bool](Test-AdWakeTapAllowed ([IntPtr]1) (Get-Date) 'fixture')
}
ConvertTo-Json -Compress $results
'''
        result = run_powershell(command)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([False, True, False, False, False, False], json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
