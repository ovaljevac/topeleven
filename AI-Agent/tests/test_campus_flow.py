import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("campus_x_detector", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


class CampusFlowTests(unittest.TestCase):
    def strip_image(self):
        image = x_detector.np.zeros((632, 1094, 3), dtype=x_detector.np.uint8)
        image[160:600, 570:1040] = 245
        for x, fill in ((40, 100), (180, 90), (320, 80)):
            image[480:507, x:x+100] = 230
            image[480:507, x:x+fill] = (45, 210, 45)
        return image

    def test_strip_distinguishes_full_and_incomplete_cards(self):
        strip = x_detector._campus_object_strip(self.strip_image())
        self.assertTrue(strip['verified'])
        self.assertEqual([False, True, True], [c['incomplete'] for c in strip['cards']])
        self.assertTrue(all(c['x'] < .5 and .8 < c['y'] < .94 for c in strip['cards']))

    def test_strip_without_detail_panel_cannot_authorize_navigation(self):
        image = self.strip_image()
        image[:, 570:] = 0
        self.assertFalse(x_detector._campus_object_strip(image)['verified'])

    def test_strip_swipe_stays_left_and_releases_mouse_on_cancellation(self):
        script = (ROOT / 'TopElevenAgent.ps1').read_text(encoding='utf-8-sig')
        start = script.index('function Move-CampusObjectStrip')
        end = script.index('function Run-CampusAutomation', start)
        flow = script[start:end]
        self.assertIn('if ($TowardsRight) { 0.455 } else { 0.065 }', flow)
        self.assertIn('finally { [Win32Agent]::mouse_event(0x0004', flow)
        self.assertIn('$endChecks -ge 2', flow)
        self.assertIn('$watched -ge 12', flow)
        self.assertNotIn('zatvori detalj', flow)

    def load(self, number):
        return x_detector.load_image(ROOT / "Kampus" / f"{number}.png")

    def test_campus_screen_finds_tool_button(self):
        result = x_detector.detect_campus_flow(self.load(3))
        self.assertEqual("campus", result["state"])
        self.assertIsNotNone(result["toolButton"])
        self.assertLess(result["maintenanceBadgeCount"], 3)

    def test_maintenance_screen(self):
        result = x_detector.detect_campus_flow(self.load(4))
        self.assertEqual("campus_maintenance", result["state"])
        self.assertIsNotNone(result["toolButton"])
        self.assertGreaterEqual(result["maintenanceBadgeCount"], 3)

    def test_maintenance_state_survives_camera_pan_zoom_and_perspective(self):
        image = self.load(4)
        height, width = image.shape[:2]
        transform = x_detector.np.array(
            [
                [1.0, 0.08, -0.04 * width],
                [-0.02, 1.02, 0.01 * height],
                [0.00012, -0.00008, 1.0],
            ],
            dtype=x_detector.np.float64,
        )
        moved = x_detector.cv2.warpPerspective(
            image,
            transform,
            (width, height),
            borderMode=x_detector.cv2.BORDER_REFLECT,
        )
        result = x_detector.detect_campus_flow(moved)
        self.assertEqual("campus_maintenance", result["state"])
        self.assertGreaterEqual(result["maintenanceBadgeCount"], 3)

    def test_green_buttons_on_other_screens_are_not_campus_maintenance(self):
        for relative in (
            Path("Mourinho") / "2.png",
            Path("Put saveza") / "5.png",
            Path("Put saveza") / "6.png",
        ):
            with self.subTest(relative=str(relative)):
                image = x_detector.load_image(ROOT / relative)
                result = x_detector.detect_campus_flow(image)
                self.assertNotEqual("campus_maintenance", result["state"])

    def test_detail_requires_exact_100_percent_text(self):
        for number in (5, 6):
            with self.subTest(number=number):
                result = x_detector.detect_campus_flow(self.load(number))
                self.assertEqual("campus_detail", result["state"])
                self.assertIsNotNone(result["hundredButtonVisible"])
                self.assertIsNotNone(result["hundredButton"])
                self.assertGreaterEqual(result["hundredButton"]["textScore"], 0.60)

    def test_plain_blue_detail_button_is_rejected(self):
        image = self.load(5)
        image[462:496, 918:1034] = (235, 170, 65)
        result = x_detector.detect_campus_flow(image)
        self.assertEqual("campus_detail", result["state"])
        self.assertIsNotNone(result["hundredButtonVisible"])
        self.assertIsNone(result["hundredButton"])

    def test_detail_without_blue_reward_area_is_not_reward_eligible(self):
        image = self.load(5)
        image[450:510, 895:1055] = (235, 235, 235)
        result = x_detector.detect_campus_flow(image)
        self.assertEqual("campus_detail", result["state"])
        self.assertIsNone(result["hundredButtonVisible"])
        self.assertIsNone(result["hundredButton"])

    def test_workflow_requires_grounding_and_fresh_maintenance_before_click(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        grounding_gate = script.index(
            "$null -eq $vision.coordinateGrounding -or -not [bool]$vision.coordinateGrounding.ok"
        )
        fresh_gate = script.index("$freshCampusGate = Get-CampusFlowSnapshot $Handle")
        object_click = script.index(
            "Click-Relative $Handle $selection.x $selection.y 'Kampus objekat ispod 100% - AI'"
        )
        self.assertLess(grounding_gate, object_click)
        self.assertLess(fresh_gate, object_click)
        same_target_gate = script.index("$sameFailedTarget = @(")
        self.assertLess(same_target_gate, object_click)

    def test_campus_waits_three_seconds_then_uses_ai_for_tool_icon(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        config = (ROOT / "config.json").read_text(encoding="utf-8")
        self.assertIn("$script:CampusOpenBufferMs = 3000", script)
        self.assertIn('"campusOpenBufferMs": 3000', config)
        self.assertIn("function Get-AiCampusToolButton", script)
        start = script.index("function Run-CampusAutomation")
        end = script.index("function Invoke-CombinedStage", start)
        flow = script[start:end]
        wait_index = flow.index("Wait-Agent $script:CampusOpenBufferMs")
        ai_index = flow.index("Get-AiCampusToolButton $Handle", wait_index)
        click_index = flow.index("'Kampus alat - AI'", ai_index)
        self.assertLess(wait_index, ai_index)
        self.assertLess(ai_index, click_index)
        self.assertNotIn("$campusSnapshot.toolButton", flow)


if __name__ == "__main__":
    unittest.main()
