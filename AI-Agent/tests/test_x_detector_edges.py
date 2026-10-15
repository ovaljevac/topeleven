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
    def tiny_close_frame(self):
        return x_detector.cv2.imread(str(Path(__file__).with_name(
            'kingshot-tiny-close-20261008.png')))

    def test_kingshot_tiny_x_is_centered_from_all_logged_ai_points(self):
        image = self.tiny_close_frame()
        for x, y in ((.858, .068), (.857, .073), (.860, .074), (.859, .073)):
            result = x_detector.refine_close_x_near_point(image, x, y)
            self.assertTrue(result['found'], result)
            self.assertGreaterEqual(result['shape'], 82)
            self.assertAlmostEqual(311, result['x']*361, delta=1)
            self.assertAlmostEqual(47.5, result['y']*616, delta=1)

    def test_tiny_x_survives_debug_jpeg_and_larger_screenshots(self):
        image = self.tiny_close_frame()
        _, encoded = x_detector.cv2.imencode('.jpg', image, [x_detector.cv2.IMWRITE_JPEG_QUALITY, 92])
        jpeg = x_detector.cv2.imdecode(encoded, x_detector.cv2.IMREAD_COLOR)
        for frame in (jpeg, x_detector.cv2.resize(image, None, fx=1.5, fy=1.5),
                      x_detector.cv2.resize(image, None, fx=2, fy=2)):
            result = x_detector.refine_close_x_near_point(frame, .857, .073)
            self.assertTrue(result['found'], result)
            self.assertAlmostEqual(311/361, result['x'], delta=.006)
            self.assertAlmostEqual(47.5/616, result['y'], delta=.006)

    def test_empty_ring_plus_and_arrow_cannot_replace_tiny_x(self):
        image = self.tiny_close_frame()
        image[41:54, 304:319] = image[37, 310]
        for kind in ('empty', 'circle', 'plus', 'arrow'):
            frame = image.copy()
            if kind == 'circle':
                x_detector.cv2.circle(frame, (311, 47), 6, (200, 200, 200), 1)
            elif kind == 'plus':
                x_detector.cv2.line(frame, (308, 48), (316, 48), (240, 240, 240), 1)
                x_detector.cv2.line(frame, (312, 44), (312, 52), (240, 240, 240), 1)
            elif kind == 'arrow':
                x_detector.cv2.line(frame, (308, 44), (312, 48), (240, 240, 240), 1)
                x_detector.cv2.line(frame, (312, 48), (308, 52), (240, 240, 240), 1)
            with self.subTest(kind=kind):
                self.assertFalse(x_detector.refine_close_x_near_point(frame, .857, .073)['found'])

    def test_tiny_x_outside_ai_neighborhood_does_not_authorize_click(self):
        self.assertFalse(x_detector.refine_close_x_near_point(
            self.tiny_close_frame(), .5, .073)['found'])

    def test_kingshot_disclosure_wins_over_larger_logo_after_wake(self):
        image = x_detector.cv2.imread(str(Path(__file__).with_name(
            'kingshot-store-badge-20261008.png')))
        for scale in (1, 1.25, 1.5, 2):
            with self.subTest(scale=scale):
                frame = x_detector.cv2.resize(image, None, fx=scale, fy=scale)
                badge = x_detector.detect_top_edge_google_play_badge(frame)
                self.assertTrue(badge['found'])
                # Visible disclosure spans x=10..58, y=40..54 at native size.
                self.assertTrue(10/361 < badge['x'] < 58/361)
                self.assertTrue(40/616 < badge['y'] < 54/616)
                self.assertAlmostEqual(34.5/361, badge['x'], delta=.003)

    def test_kingshot_logo_alone_cannot_replace_missing_disclosure(self):
        image = x_detector.cv2.imread(str(Path(__file__).with_name(
            'kingshot-store-badge-20261008.png')))
        image[38:54, 8:60] = image[38, 65]
        self.assertFalse(x_detector.detect_top_edge_google_play_badge(image)['found'])

    def test_detects_orange_upper_left_filled_fast_forward_skip(self):
        image = x_detector.np.zeros((615, 1067, 3), dtype=x_detector.np.uint8)
        image[54:126, :] = (0, 165, 245)
        glyph = (
            "#.......##.....##",
            "###.....###....##",
            "#####...#####..##",
            "#######.#########",
            "#################",
            "#######.######.##",
            "#####...#####..##",
            "###.....###....##",
            "#.......#......##",
        )
        for row_index, row in enumerate(glyph):
            for column_index, value in enumerate(row):
                if value == "#":
                    image[72 + row_index, 25 + column_index] = (255, 255, 255)

        result = x_detector._detect_double_chevron_control(image)

        self.assertIsNotNone(result)
        self.assertEqual("skip", result["kind"])
        self.assertEqual("left", result["side"])
        self.assertLess(result["x"], 0.08)

    def test_rejects_playable_resource_artwork_inside_right_edge(self):
        image = x_detector.np.zeros((614, 1066, 3), dtype=x_detector.np.uint8)
        points = x_detector.np.array(
            [[919, 88], [929, 80], [940, 88], [929, 95]],
            dtype=x_detector.np.int32,
        )
        x_detector.cv2.polylines(
            image, [points], True, (255, 255, 255), 2, x_detector.cv2.LINE_AA
        )

        result = x_detector._detect_double_chevron_control(image)

        self.assertIsNone(result)

    def test_dense_left_branding_does_not_beat_isolated_right_skip(self):
        image = x_detector.np.full((614, 1068, 3), 185, dtype=x_detector.np.uint8)
        x_detector.cv2.putText(
            image, "WHITEOUT", (8, 62), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.65, (255, 255, 255), 2, x_detector.cv2.LINE_AA,
        )
        x_detector.cv2.putText(
            image, "SURVIVAL", (8, 88), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.58, (255, 255, 255), 2, x_detector.cv2.LINE_AA,
        )
        for offset in (0, 9):
            points = x_detector.np.array(
                [[1000 + offset, 67], [1007 + offset, 75], [1000 + offset, 83]],
                dtype=x_detector.np.int32,
            )
            x_detector.cv2.polylines(
                image, [points], False, (255, 255, 255), 2, x_detector.cv2.LINE_AA
            )

        result = x_detector._detect_double_chevron_control(image)

        self.assertIsNotNone(result)
        self.assertEqual("skip", result["kind"])
        self.assertGreater(result["x"], 0.90)

    def test_dense_left_branding_alone_is_not_a_skip(self):
        image = x_detector.np.full((614, 1068, 3), 185, dtype=x_detector.np.uint8)
        x_detector.cv2.putText(
            image, "WHITEOUT", (8, 62), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.65, (255, 255, 255), 2, x_detector.cv2.LINE_AA,
        )
        x_detector.cv2.putText(
            image, "SURVIVAL", (8, 88), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.58, (255, 255, 255), 2, x_detector.cv2.LINE_AA,
        )

        self.assertIsNone(x_detector._detect_double_chevron_control(image))

    def test_detects_neutral_left_edge_fast_forward_skip(self):
        image = x_detector.np.zeros((615, 1067, 3), dtype=x_detector.np.uint8)
        x_detector.cv2.circle(image, (33, 76), 18, (145, 155, 165), -1)
        x_detector.cv2.putText(
            image, ">>", (24, 81), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.45, (255, 255, 255), 1, x_detector.cv2.LINE_AA,
        )
        result = x_detector._detect_double_chevron_control(image)
        self.assertIsNotNone(result)
        self.assertEqual("skip", result["kind"])
        self.assertEqual("left", result["side"])
        self.assertLess(result["x"], 0.14)

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

    def test_detects_branded_bottom_right_google_play_badge(self):
        image = x_detector.np.full((632, 1084, 3), (155, 175, 190), dtype=x_detector.np.uint8)
        x1, y1, x2, y2 = 870, 560, 1020, 605
        x_detector.cv2.rectangle(image, (x1, y1), (x2, y2), (5, 5, 5), -1)
        x_detector.cv2.rectangle(image, (882, 570), (891, 591), (40, 205, 40), -1)
        x_detector.cv2.rectangle(image, (892, 570), (901, 591), (20, 210, 245), -1)
        x_detector.cv2.rectangle(image, (902, 570), (911, 591), (230, 90, 35), -1)
        x_detector.cv2.rectangle(image, (912, 570), (921, 591), (40, 40, 230), -1)
        x_detector.cv2.putText(
            image, "Google Play", (928, 590), x_detector.cv2.FONT_HERSHEY_SIMPLEX,
            0.42, (245, 245, 245), 1, x_detector.cv2.LINE_AA,
        )

        result = x_detector.detect_yellow_ad_control(image)

        self.assertTrue(result["found"])
        self.assertEqual("google_play", result["kind"])
        self.assertEqual("bottom-right-google-play-badge", result["method"])
        self.assertGreater(result["y"], 0.84)

    def test_detects_dark_x_on_white_install_overlay(self):
        image = x_detector.np.full((615, 1067, 3), 245, dtype=x_detector.np.uint8)
        # BlueStacks toolbar begins after the app viewport and must not become
        # part of the candidate component.
        image[:, 1034:] = (40, 40, 40)
        x_detector.cv2.line(image, (1001, 60), (1013, 72), (115, 115, 115), 2)
        x_detector.cv2.line(image, (1013, 60), (1001, 72), (115, 115, 115), 2)

        result = x_detector.detect_x(image, live=True)

        self.assertIsNotNone(result)
        self.assertEqual("close", result["kind"])
        self.assertAlmostEqual(1007 / 1067, result["x"], delta=0.005)
        self.assertAlmostEqual(66 / 615, result["y"], delta=0.01)

    def test_light_install_overlay_x_refines_nearby_ai_coordinate(self):
        image = x_detector.np.full((615, 1067, 3), 245, dtype=x_detector.np.uint8)
        image[:, 1034:] = (40, 40, 40)
        x_detector.cv2.line(image, (1001, 60), (1013, 72), (115, 115, 115), 2)
        x_detector.cv2.line(image, (1013, 60), (1001, 72), (115, 115, 115), 2)

        result = x_detector.refine_close_x_near_point(image, 0.943, 0.108)

        self.assertTrue(result["found"])
        self.assertEqual("ai-local-light-overlay-component", result["method"])


if __name__ == "__main__":
    unittest.main()
