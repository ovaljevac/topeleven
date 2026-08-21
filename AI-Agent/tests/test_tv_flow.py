import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tv_x_detector", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


class TvFlowTests(unittest.TestCase):
    def load(self, number):
        return x_detector.load_image(ROOT / "za TV skriptu" / f"{number}.png")

    def test_home_reference(self):
        result = x_detector.detect_tv_flow(self.load(1))
        self.assertEqual("home", result["state"])
        self.assertIsNotNone(result["tvButton"])
        self.assertAlmostEqual(0.83, result["tvButton"]["x"], delta=0.03)

    def test_tv_screen_finds_three_watch_buttons(self):
        result = x_detector.detect_tv_flow(self.load(2))
        self.assertEqual("tv", result["state"])
        self.assertEqual(3, len(result["buttons"]))
        self.assertFalse(result["buttons"][0]["manual"])
        self.assertTrue(result["buttons"][2]["manual"])
        self.assertTrue(all(button["textScore"] >= 0.55 for button in result["buttons"]))

    def test_plain_blue_rectangle_is_not_watch_button(self):
        image = self.load(2)
        image[558:588, 85:195] = (240, 170, 70)
        result = x_detector.detect_tv_flow(image)
        self.assertEqual(2, len(result["buttons"]))

    def test_manual_reward_stages(self):
        for number in (3, 4, 5):
            with self.subTest(number=number):
                result = x_detector.detect_tv_flow(self.load(number))
                self.assertEqual(f"manual_{number}", result["state"])
        result = x_detector.detect_tv_flow(self.load(5))
        self.assertIsNotNone(result["continueButton"])
        self.assertGreaterEqual(result["continueButton"]["textScore"], 0.65)

    def test_full_width_continue_button(self):
        image = self.load(5)
        original_button = image[573:608, 301:539].copy()
        green = tuple(int(value) for value in image[580, 310])
        image[573:608, 35:1065] = green
        image[573:608, 430:668] = original_button

        result = x_detector.detect_tv_flow(image)
        self.assertEqual("manual_5", result["state"])
        self.assertIsNotNone(result["continueButton"])
        self.assertGreater(result["continueButton"]["x"], 0.45)
        self.assertLess(result["continueButton"]["x"], 0.55)

    def test_plain_green_continue_button_is_rejected(self):
        image = self.load(5)
        green = tuple(int(value) for value in image[580, 310])
        image[573:608, 301:539] = green
        result = x_detector.detect_tv_flow(image)
        self.assertEqual("manual_5", result["state"])
        self.assertIsNone(result["continueButton"])


if __name__ == "__main__":
    unittest.main()
