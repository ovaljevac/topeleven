import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("x_detector", ROOT / "XDetector.py")
x_detector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(x_detector)


def candidate(x):
    return {
        "found": True,
        "x": x,
        "y": 0.10,
        "score": 265.0,
        "polarity": "bright-on-dark",
        "method": "response",
        "shape": 82.0,
        "kind": "close",
    }


class GuardedEdgeTests(unittest.TestCase):
    def test_real_close_has_priority_over_false_reward_chevron(self):
        original_skip = x_detector._detect_double_chevron_control
        original_right = x_detector._detect_right_corner_x
        try:
            x_detector._detect_double_chevron_control = lambda image: {
                "found": True,
                "x": 0.885,
                "y": 0.090,
                "score": 500.0,
                "kind": "skip",
            }
            x_detector._detect_right_corner_x = lambda image, live=False: {
                "found": True,
                "x": 0.949,
                "y": 0.089,
                "score": 354.0,
                "kind": "close",
            }
            image = x_detector.np.zeros((632, 1096, 3), dtype=x_detector.np.uint8)
            result = x_detector.detect_x(image)
            self.assertEqual("close", result["kind"])
            self.assertAlmostEqual(0.949, result["x"])
        finally:
            x_detector._detect_double_chevron_control = original_skip
            x_detector._detect_right_corner_x = original_right

    def setUp(self):
        self.image = x_detector.np.zeros((600, 400, 3), dtype=x_detector.np.uint8)

    def run_with_corner_results(self, first, second):
        with mock.patch.object(x_detector, "_detect_double_chevron_control", return_value=None), mock.patch.object(
            x_detector, "_detect_right_corner_x", side_effect=[first, second]
        ):
            return x_detector.detect_x(self.image, live=True)

    def test_rejects_false_left_control_at_15_9_percent(self):
        result = self.run_with_corner_results(None, candidate(0.841))
        self.assertIsNone(result)

    def test_accepts_real_left_edge_control(self):
        result = self.run_with_corner_results(None, candidate(0.974))
        self.assertAlmostEqual(0.026, result["x"], places=3)
        self.assertEqual("left", result["side"])

    def test_rejects_right_control_before_guarded_edge(self):
        result = self.run_with_corner_results(candidate(0.84), None)
        self.assertIsNone(result)

    def test_detects_neutral_google_play_counter_badge(self):
        image = x_detector.np.zeros((632, 1084, 3), dtype=x_detector.np.uint8)
        x_detector.cv2.rectangle(image, (915, 56), (1036, 107), (70, 70, 70), -1)
        x_detector.cv2.rectangle(image, (915, 56), (1036, 107), (245, 245, 245), 3)
        x_detector.cv2.circle(image, (1010, 84), 14, (0, 175, 255), -1)
        x_detector.cv2.putText(
            image, "3", (960, 94), x_detector.cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2
        )
        result = x_detector.detect_yellow_ad_control(image)
        self.assertTrue(result["found"])
        self.assertEqual("google_play", result["kind"])

    def test_neutral_skip_without_coin_is_not_google_play(self):
        image = x_detector.np.zeros((632, 1084, 3), dtype=x_detector.np.uint8)
        x_detector.cv2.rectangle(image, (915, 56), (1036, 107), (70, 70, 70), -1)
        x_detector.cv2.rectangle(image, (915, 56), (1036, 107), (245, 245, 245), 3)
        x_detector.cv2.putText(
            image, ">>", (975, 94), x_detector.cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
        )
        self.assertFalse(x_detector.detect_yellow_ad_control(image)["found"])

    def test_detects_tiny_top_left_google_play_badge_at_pixel_center(self):
        image = x_detector.np.full(
            (633, 370, 3), (40, 110, 190), dtype=x_detector.np.uint8
        )
        x_detector.cv2.rectangle(image, (8, 42), (67, 58), (55, 55, 55), -1)
        x_detector.cv2.putText(
            image,
            "Google Play",
            (17, 54),
            x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.28,
            (245, 245, 245),
            1,
            x_detector.cv2.LINE_AA,
        )
        triangle = x_detector.np.array(
            [[10, 46], [10, 54], [16, 50]], x_detector.np.int32
        )
        x_detector.cv2.fillConvexPoly(image, triangle, (245, 245, 245))

        result = x_detector.detect_yellow_ad_control(image)
        self.assertTrue(result["found"])
        self.assertEqual("google_play", result["kind"])
        self.assertEqual("top-left-google-play-badge", result["method"])
        self.assertLess(result["y"], 0.09)


if __name__ == "__main__":
    unittest.main()
