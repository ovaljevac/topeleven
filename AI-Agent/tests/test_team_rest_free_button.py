import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pydeps"))

import cv2
import numpy as np

SPEC = importlib.util.spec_from_file_location("x_detector_team_rest", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = x_detector
SPEC.loader.exec_module(x_detector)


def team_rest_screen(label):
    image = np.zeros((632, 1094, 3), dtype=np.uint8)
    image[42:67, 560:580] = (40, 200, 40)
    image[42:67, 610:630] = (220, 80, 40)
    image[42:67, 660:680] = (40, 40, 220)
    x, y, width, height = 753, 526, 145, 60
    image[y:y + height, x:x + width] = (215, 160, 70)
    if label == "ready":
        font_scale = 0.60
        text_size, _ = cv2.getTextSize(
            "BESPLATNO", cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )
        text_x = x + (width - text_size[0]) // 2
        text_y = y + (height + text_size[1]) // 2
        cv2.putText(
            image,
            "BESPLATNO",
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    elif label == "loading":
        for offset in (-12, 0, 12):
            cv2.circle(image, (x + width // 2 + offset, y + height // 2), 3, (255, 255, 255), -1)
    return image


class TeamRestFreeButtonTests(unittest.TestCase):
    def test_full_besplatno_label_is_ready(self):
        result = x_detector.detect_team_rest_free_button(team_rest_screen("ready"))
        self.assertTrue(result["found"])
        self.assertTrue(result["ready"])
        self.assertGreaterEqual(result["glyphCount"], 8)

    def test_three_loading_dots_are_not_ready(self):
        result = x_detector.detect_team_rest_free_button(team_rest_screen("loading"))
        self.assertFalse(result["found"])
        self.assertFalse(result["ready"])
        self.assertTrue(result["buttonVisible"])

    def test_plain_blue_button_is_not_ready(self):
        result = x_detector.detect_team_rest_free_button(team_rest_screen("plain"))
        self.assertFalse(result["found"])
        self.assertFalse(result["ready"])

    def test_ready_label_survives_window_scaling(self):
        source = team_rest_screen("ready")
        for scale in (0.75, 1.25):
            resized = cv2.resize(
                source,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_LINEAR,
            )
            with self.subTest(scale=scale):
                self.assertTrue(
                    x_detector.detect_team_rest_free_button(resized)["ready"]
                )


if __name__ == "__main__":
    unittest.main()
