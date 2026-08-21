import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mourinho_x_detector", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


class MourinhoFlowTests(unittest.TestCase):
    def load(self, number):
        return x_detector.load_image(ROOT / "Mourinho" / f"{number}.png")

    def test_main_screen(self):
        result = x_detector.detect_mourinho_flow(self.load(1))
        self.assertEqual("mourinho_home", result["state"])
        self.assertIsNone(result["button"])
        self.assertIsNotNone(result["warning"])
        self.assertAlmostEqual(0.51, result["warning"]["x"], delta=0.02)

    def test_yellow_warning_can_move_right(self):
        image = self.load(1)
        image[555:592, 538:582] = (238, 238, 238)
        x1, y1, x2, y2 = 590, 552, 625, 583
        x_detector.cv2.rectangle(image, (x1, y1), (x2, y2), (40, 205, 235), -1)
        x_detector.cv2.line(image, (607, 559), (607, 573), (45, 45, 45), 4)
        x_detector.cv2.circle(image, (607, 578), 2, (45, 45, 45), -1)

        result = x_detector.detect_mourinho_flow(image)
        self.assertEqual("mourinho_home", result["state"])
        self.assertIsNotNone(result["warning"])
        self.assertAlmostEqual(607.5 / image.shape[1], result["warning"]["x"], delta=0.01)

    def test_popup_requires_watch_text(self):
        result = x_detector.detect_mourinho_flow(self.load(2))
        self.assertEqual("mourinho_popup", result["state"])
        self.assertIsNotNone(result["button"])
        self.assertGreaterEqual(result["button"]["textScore"], 0.55)

    def test_plain_blue_popup_button_is_rejected(self):
        image = self.load(2)
        image[341:370, 725:842] = (240, 170, 70)
        result = x_detector.detect_mourinho_flow(image)
        self.assertEqual("mourinho_popup", result["state"])
        self.assertIsNone(result["button"])

    def test_top_resource_bar_confirms_app_return(self):
        for number in (1, 2):
            with self.subTest(number=number):
                result = x_detector.detect_top_resource_cards(self.load(number))
                self.assertTrue(result["found"])
                self.assertGreaterEqual(result["green"], 100)
                self.assertGreaterEqual(result["blue"], 70)
                self.assertGreaterEqual(result["red"], 70)


if __name__ == "__main__":
    unittest.main()
