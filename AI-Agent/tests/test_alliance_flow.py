import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pydeps"))

import cv2


SPEC = importlib.util.spec_from_file_location("alliance_x_detector", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


class AllianceFlowTests(unittest.TestCase):
    def load(self, number):
        return x_detector.load_image(ROOT / "Put saveza" / f"{number}.png")

    def test_closed_navigation_has_dynamic_menu_toggle(self):
        result = x_detector.detect_alliance_flow(self.load(1))
        self.assertEqual("home", result["state"])
        self.assertIsNotNone(result["menuToggle"])
        self.assertLess(result["menuToggle"]["x"], 0.03)

    def test_top_sidebar_finds_home_and_campus_but_not_alliance(self):
        result = x_detector.detect_alliance_flow(self.load(2))
        self.assertEqual("side_menu", result["state"])
        self.assertIsNotNone(result["homeButton"])
        self.assertIsNotNone(result["campusButton"])
        self.assertIsNone(result["allianceButton"])

    def test_scrolled_sidebar_finds_alliance_despite_desktop_overlay(self):
        result = x_detector.detect_alliance_flow(self.load(3))
        self.assertEqual("side_menu", result["state"])
        self.assertIsNotNone(result["allianceButton"])
        self.assertAlmostEqual(0.08, result["allianceButton"]["x"], delta=0.03)
        self.assertAlmostEqual(0.55, result["allianceButton"]["y"], delta=0.05)

    def test_alliance_screen_finds_path_tile(self):
        result = x_detector.detect_alliance_flow(self.load(4))
        self.assertEqual("alliance", result["state"])
        self.assertIsNotNone(result["pathButton"])
        self.assertGreater(result["pathButton"]["y"], 0.78)

    def test_path_modal_finds_only_exact_blue_video_idi_and_local_x(self):
        result = x_detector.detect_alliance_flow(self.load(5))
        self.assertEqual("path", result["state"])
        self.assertTrue(result["dailyTaskPresent"])
        self.assertFalse(result["completedLayout"])
        self.assertTrue(result["taskGridLoaded"])
        self.assertIsNotNone(result["goButtonVisible"])
        self.assertIsNotNone(result["goButton"])
        self.assertGreaterEqual(result["goButton"]["textScore"], 0.60)
        self.assertIsNotNone(result["closeButton"])
        self.assertAlmostEqual(0.916, result["closeButton"]["x"], delta=0.02)
        self.assertAlmostEqual(0.124, result["closeButton"]["y"], delta=0.02)

    def test_completed_path_ignores_every_green_idi(self):
        result = x_detector.detect_alliance_flow(self.load(6))
        self.assertEqual("path", result["state"])
        self.assertFalse(result["dailyTaskPresent"])
        self.assertTrue(result["completedLayout"])
        self.assertTrue(result["taskGridLoaded"])
        self.assertIsNone(result["goButtonVisible"])
        self.assertIsNone(result["goButton"])
        self.assertIsNotNone(result["closeButton"])

    def test_plain_blue_or_loading_button_is_never_ready(self):
        image = self.load(5)
        fill = tuple(int(value) for value in image[260, 320])
        image[255:282, 310:384] = fill
        result = x_detector.detect_alliance_flow(image)
        self.assertEqual("path", result["state"])
        self.assertIsNotNone(result["goButtonVisible"])
        self.assertIsNone(result["goButton"])

    def test_video_icon_with_three_loading_dots_is_not_idi(self):
        image = self.load(5)
        fill = tuple(int(value) for value in image[260, 320])
        image[255:282, 347:384] = fill
        for x in (355, 363, 371):
            cv2.circle(image, (x, 268), 2, (255, 255, 255), -1)
        result = x_detector.detect_alliance_flow(image)
        self.assertEqual("path", result["state"])
        self.assertIsNotNone(result["goButtonVisible"])
        self.assertIsNone(result["goButton"])

    def test_bluestacks_titlebar_x_cannot_replace_erased_modal_x(self):
        image = self.load(5)
        fill = tuple(int(value) for value in image[100, 990])
        image[63:98, 995:1040] = fill
        result = x_detector.detect_alliance_flow(image)
        self.assertEqual("path", result["state"])
        self.assertIsNone(result["closeButton"])

    def test_detector_survives_window_resizing(self):
        for scale in (0.70, 0.80, 0.90, 1.10, 1.20):
            for number, expected in (
                (3, "side_menu"), (4, "alliance"), (5, "path"), (6, "path")
            ):
                with self.subTest(scale=scale, number=number):
                    image = self.load(number)
                    resized = cv2.resize(image, None, fx=scale, fy=scale)
                    result = x_detector.detect_alliance_flow(resized)
                    self.assertEqual(expected, result["state"])
                    if number == 3:
                        self.assertAlmostEqual(0.08, result["allianceButton"]["x"], delta=0.03)
                    if number == 4:
                        self.assertGreater(result["pathButton"]["y"], 0.78)
                    if number == 5:
                        self.assertIsNotNone(result["goButton"])
                        self.assertAlmostEqual(0.916, result["closeButton"]["x"], delta=0.025)
                    if number == 6:
                        self.assertTrue(result["completedLayout"])
                        self.assertIsNone(result["goButton"])
                        self.assertAlmostEqual(0.919, result["closeButton"]["x"], delta=0.025)

    def test_server_dispatch_uses_alliance_flow(self):
        result = x_detector.run_detector(self.load(4), "alliance_flow")
        self.assertEqual("alliance", result["state"])


if __name__ == "__main__":
    unittest.main()
