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


def function_body(source, name):
    start = source.index(f"function {name}")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"PowerShell function {name!r} has no closing brace")


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


def green_store_screen(label):
    image = np.zeros((632, 1094, 3), dtype=np.uint8)
    image[42:67, 560:580] = (40, 200, 40)
    image[42:67, 610:630] = (220, 80, 40)
    image[42:67, 660:680] = (40, 40, 220)
    image[190:342, 22:241] = (235, 235, 235)
    x, y, width, height = 883, 130, 168, 50
    image[y:y + height, x:x + width] = (215, 160, 70)
    cv2.circle(image, (x + width - 13, y + height // 2), 11, (30, 190, 45), -1)
    cv2.putText(image, "G", (x + width - 18, y + height // 2 + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    if label == "ready":
        text_size, _ = cv2.getTextSize("BESPLATNO", cv2.FONT_HERSHEY_SIMPLEX, 0.60, 1)
        cv2.putText(
            image,
            "BESPLATNO",
            (x + (width - text_size[0]) // 2, y + (height + text_size[1]) // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    elif label == "loading":
        for offset in (-12, 0, 12):
            cv2.circle(image, (x + width // 2 + offset, y + height // 2), 3, (255, 255, 255), -1)
    return image


def green_store_lower_screen(label):
    image = green_store_screen("plain")
    image[130:180, 883:1051] = 0
    x, y, width, height = 883, 350, 168, 50
    image[y:y + height, x:x + width] = (215, 160, 70)
    cv2.circle(image, (x + width - 13, y + height // 2), 11, (30, 190, 45), -1)
    cv2.putText(image, "G", (x + width - 18, y + height // 2 + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    if label == "ready":
        text_size, _ = cv2.getTextSize("BESPLATNO", cv2.FONT_HERSHEY_SIMPLEX, 0.60, 1)
        cv2.putText(
            image,
            "BESPLATNO",
            (x + (width - text_size[0]) // 2, y + (height + text_size[1]) // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return image


def _draw_store_reward_row(image, label, x=883, y=350, width=168, height=50):
    center_y = y + height // 2
    # Video icon + resource icon are the stable Store reward-button context.
    cv2.rectangle(image, (x + 5, center_y - 7), (x + 27, center_y + 7), (255, 255, 255), -1)
    cv2.circle(image, (x + 28, center_y), 7, (255, 255, 255), -1)
    cv2.circle(image, (x + width - 13, center_y), 11, (30, 190, 45), -1)
    cv2.putText(image, "G", (x + width - 18, center_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (255, 255, 255), 1, cv2.LINE_AA)
    if label == "loading":
        for offset in (-12, 0, 12):
            cv2.circle(image, (x + width // 2 + offset, center_y), 3, (255, 255, 255), -1)
        return
    text = "BESPLATNO" if label == "ready" else label
    if text and text != "plain":
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        text_x = x + 35 + max(0, (width - 70 - text_size[0]) // 2)
        cv2.putText(image, text, (text_x, center_y + text_size[1] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)


def green_store_connected_background_screen(label, flanked=True):
    image = green_store_screen("plain")
    # Spoji plavi button s velikom povrsinom iste boje, kao na stvarnom
    # ekranu Prodavnice gdje contour dugmeta vise nije zasebna komponenta.
    image[180:500, 820:1094] = (215, 160, 70)
    x, y, width, height = 883, 350, 168, 50
    if flanked:
        _draw_store_reward_row(image, label, x, y, width, height)
    elif label and label != "plain":
        text = "BESPLATNO" if label == "ready" else label
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 1)
        cv2.putText(image, text, (x + (width - text_size[0]) // 2,
                                  y + (height + text_size[1]) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 1, cv2.LINE_AA)
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

    def test_green_store_full_label_is_fast_dynamic_candidate(self):
        result = x_detector.detect_team_rest_free_button(green_store_screen("ready"))
        self.assertTrue(result["ready"])
        self.assertTrue(result["storeLoaded"])
        self.assertEqual("store", result["layout"])
        self.assertAlmostEqual(0.884, result["x"], delta=0.02)
        self.assertAlmostEqual(0.245, result["y"], delta=0.02)

    def test_green_store_loading_dots_are_not_ready(self):
        result = x_detector.detect_team_rest_free_button(green_store_screen("loading"))
        self.assertTrue(result["storeLoaded"])
        self.assertTrue(result["buttonVisible"])
        self.assertFalse(result["ready"])

    def test_green_store_button_can_be_lower_in_offer_list(self):
        result = x_detector.detect_team_rest_free_button(green_store_lower_screen("ready"))
        self.assertTrue(result["ready"])
        self.assertEqual("store", result["layout"])
        self.assertAlmostEqual(0.593, result["y"], delta=0.02)

    def test_store_text_is_found_when_blue_button_merges_with_background(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("ready")
        )
        self.assertTrue(result["ready"])
        self.assertTrue(result.get("textFirst"))

    def test_text_first_detector_groups_split_antialiased_letter_components(self):
        detector = (ROOT / "XDetector.py").read_text(encoding="utf-8")
        self.assertIn("camera_index = next(", detector)
        self.assertIn("row = row[camera_index:]", detector)
        self.assertIn("merge_tolerance = max(1.5, width * 0.002)", detector)
        self.assertIn('group["parts"] += 1', detector)

    def test_merged_store_loading_dots_are_still_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("loading")
        )
        self.assertFalse(result["ready"])

    def test_merged_store_plain_pogledaj_text_is_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("POGLEDAJ", flanked=False)
        )
        self.assertFalse(result["ready"])

    def test_icon_flanked_pogledaj_text_is_still_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("POGLEDAJ", flanked=True)
        )
        self.assertFalse(result["ready"])

    def test_blue_morale_besplatno_is_never_accepted_for_green_stage(self):
        image = green_store_connected_background_screen("ready")
        # Zamijeni desnu zelenu ikonu resursa plavom ikonom morala.
        cv2.circle(image, (883 + 168 - 13, 350 + 25), 13, (220, 80, 40), -1)
        cv2.putText(image, "M", (883 + 168 - 18, 350 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        result = x_detector.detect_team_rest_free_button(image)
        self.assertFalse(result["ready"])

    def test_merged_store_besplatni_navigation_text_is_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("BESPLATNI", flanked=False)
        )
        self.assertFalse(result["ready"])

    def test_merged_store_random_white_text_is_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("ABCDEFGH", flanked=False)
        )
        self.assertFalse(result["ready"])

    def test_icon_flanked_random_white_text_is_still_rejected(self):
        result = x_detector.detect_team_rest_free_button(
            green_store_connected_background_screen("ABCDEFGH", flanked=True)
        )
        self.assertFalse(result["ready"])

    def test_green_stage_uses_fast_snapshot_and_dynamic_button_center(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        free_ready = function_body(script, "Test-FreeButtonReady")
        store_loaded = function_body(script, "Test-StoreLoaded")

        self.assertIn("Get-TeamRestFreeButtonSnapshot $Handle", free_ready)
        self.assertIn("$script:DetectedFreeButtonX = $x", free_ready)
        self.assertIn("$script:DetectedFreeButtonY = $y", free_ready)
        self.assertNotIn("Get-ColorMatchCount", free_ready)
        self.assertIn("Get-TeamRestFreeButtonSnapshot $Handle", store_loaded)
        self.assertIn("$snapshot.storeLoaded", store_loaded)
        self.assertNotIn("Get-ColorMatchCount", store_loaded)

        green_start = script.index(
            "Invoke-StageWithRecovery 'Uzmi 25 zelenih'"
        )
        dynamic_click = script.index(
            "'BESPLATNO - dinamicki centar'", green_start
        )
        self.assertIn("$script:DetectedFreeButtonX", script[green_start:dynamic_click])
        self.assertIn("$script:DetectedFreeButtonY", script[green_start:dynamic_click])

    def test_green_stage_does_not_finish_when_next_offer_is_missing(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("if (-not $stillAvailable)", script)
        self.assertIn("if ($offer.State -eq 'limit')", script)
        self.assertIn("$offer = Wait-GreenRewardOffer $handle", script)

    def test_green_stage_restarts_only_confirmed_grey_offer(self):
        script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
        helper = function_body(script, "Wait-GreenRewardOffer")
        self.assertIn("while ($true)", helper)
        self.assertIn("if ($state -eq 'grey')", helper)
        self.assertEqual(1, helper.count("Restart-TopElevenForStageRetry"))
        self.assertIn("Open-Store $Handle", helper)

        green_start = script.index("Invoke-StageWithRecovery 'Uzmi 25 zelenih'")
        first_ad = script.index("$adStartedAt = Get-Date", green_start)
        initial_call = script.index("Wait-GreenRewardOffer", green_start)
        self.assertLess(initial_call, first_ad)


if __name__ == "__main__":
    unittest.main()
