import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vision_agent", ROOT / "VisionAgent.py")
vision_agent = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vision_agent
SPEC.loader.exec_module(vision_agent)


def decision(action="click_close", control="close_x", x=0.95, y=0.08, confidence=0.94, text="Ad"):
    return {
        "screenType": "ad",
        "topElevenReturned": False,
        "control": {"type": control, "x": x, "y": y, "confidence": confidence},
        "recommendedAction": action,
        "reason": "Visible control",
        "visibleText": text,
    }


def mourinho_decision(x=0.55, y=0.84, confidence=0.96):
    result = decision(
        action="click_target",
        control="mourinho_warning",
        x=x,
        y=y,
        confidence=confidence,
        text="Nivo spremnosti  PREGLED UTAKMICE",
    )
    result["screenType"] = "top_eleven"
    result["topElevenReturned"] = True
    return result


def campus_decision(
    x=0.43,
    y=0.63,
    confidence=0.96,
    text="TARGET: STADION; PERCENT: 60%",
):
    result = decision(
        action="click_campus_building",
        control="campus_building",
        x=x,
        y=y,
        confidence=confidence,
        text=text,
    )
    result["screenType"] = "top_eleven"
    result["topElevenReturned"] = True
    return result


def campus_none_decision():
    result = decision(
        action="none",
        control="none",
        x=None,
        y=None,
        confidence=0,
        text="All visible facilities are 100%",
    )
    result["screenType"] = "top_eleven"
    result["topElevenReturned"] = True
    return result


class VisionGuardTests(unittest.TestCase):
    def setUp(self):
        self.config = {"minimumConfidence": 0.85}

    def test_accepts_high_confidence_edge_close(self):
        normalized, errors = vision_agent.validate_decision(decision(), self.config)
        self.assertEqual([], errors)
        self.assertEqual("click_close", normalized["recommendedAction"])

    def test_rejects_install_or_get_screen(self):
        _, errors = vision_agent.validate_decision(decision(text="Install  Get"), self.config)
        self.assertIn("dangerous commerce/install text is visible", errors)

    def test_accepts_store_back_and_discards_grounded_coordinates(self):
        raw = decision(
            action="send_back",
            control="back",
            x=26,
            y=66,
            confidence=0.99,
            text="Google Play Install",
        )
        raw["screenType"] = "google_play_store"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "external_navigation_123", image_size=(1095, 631)
        )
        self.assertEqual([], errors)
        self.assertIsNone(normalized["control"]["x"])
        self.assertIsNone(normalized["control"]["y"])

    def test_accepts_chrome_play_destination_back(self):
        raw = decision(
            action="send_back",
            control="back",
            x=None,
            y=None,
            confidence=0.97,
            text="play.google.com",
        )
        raw["screenType"] = "play_google_chrome"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "external_navigation_456", image_size=(1095, 631)
        )
        self.assertEqual([], errors)
        self.assertEqual("play_google_chrome", normalized["screenType"])
        self.assertEqual("send_back", normalized["recommendedAction"])

    def test_ai_only_server_keeps_exact_ai_coordinates_without_opencv_refinement(self):
        config = {
            "minimumConfidence": 0.85,
            "requiredAgreementCount": 1,
            "coordinateTolerance": 0.035,
            "saveUnknownScreenshots": False,
        }
        server = vision_agent.VisionServer(config)
        original_request = vision_agent.request_vision_model
        original_refine = vision_agent.refine_decision_control_center
        vision_agent.request_vision_model = lambda image, expected, supplied: decision(
            x=0.913, y=0.087
        )
        vision_agent.refine_decision_control_center = lambda image, result: self.fail(
            "OpenCV refinement must not run for ad controls"
        )
        try:
            image = vision_agent.Image.new("RGB", (1095, 631), "black")
            result = server.analyze(image, "ad_control_ai_only_123")
            self.assertTrue(result["accepted"])
            self.assertEqual(0.913, result["decision"]["control"]["x"])
            self.assertEqual(0.087, result["decision"]["control"]["y"])
        finally:
            vision_agent.request_vision_model = original_request
            vision_agent.refine_decision_control_center = original_refine

    def test_ai_only_profile_return_discards_profile_x_instead_of_rejecting(self):
        raw = decision(
            action="click_training_player_close",
            control="training_player_close",
            x=0.88,
            y=0.10,
            confidence=0.99,
            text="CONDITION: 32%",
        )
        raw["screenType"] = "top_eleven"
        raw["topElevenReturned"] = True
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "ad_control_ai_only_training_player_123",
            image_size=(1048, 719),
        )
        self.assertEqual([], errors)
        self.assertEqual("none", normalized["recommendedAction"])
        self.assertEqual("none", normalized["control"]["type"])
        self.assertIsNone(normalized["control"]["x"])
        self.assertTrue(normalized["topElevenReturned"])

    def test_rejects_close_in_middle_of_screen(self):
        _, errors = vision_agent.validate_decision(decision(x=0.5, y=0.5), self.config)
        self.assertIn("close/skip coordinate outside guarded edge zone", errors)

    def test_rejects_low_confidence(self):
        _, errors = vision_agent.validate_decision(decision(confidence=0.5), self.config)
        self.assertIn("confidence below configured minimum", errors)

    def test_rejects_action_control_mismatch(self):
        _, errors = vision_agent.validate_decision(decision(action="click_close", control="google_play"), self.config)
        self.assertIn("action and control do not match", errors)

    def test_requires_two_matching_analyses(self):
        config = {
            "minimumConfidence": 0.85,
            "requiredAgreementCount": 2,
            "coordinateTolerance": 0.035,
            "saveUnknownScreenshots": False,
        }
        server = vision_agent.VisionServer(config)
        original = vision_agent.request_vision_model
        vision_agent.request_vision_model = lambda image, expected, supplied: decision()
        try:
            image = vision_agent.Image.new("RGB", (32, 32), "black")
            self.assertFalse(server.analyze(image, "ad_control")["accepted"])
            self.assertTrue(server.analyze(image, "ad_control")["accepted"])
        finally:
            vision_agent.request_vision_model = original

    def test_agreement_is_tracked_separately_per_expected_state(self):
        config = {
            "minimumConfidence": 0.85,
            "requiredAgreementCount": 2,
            "coordinateTolerance": 0.035,
            "saveUnknownScreenshots": False,
        }
        server = vision_agent.VisionServer(config)
        original = vision_agent.request_vision_model
        vision_agent.request_vision_model = lambda image, expected, supplied: decision()
        try:
            image = vision_agent.Image.new("RGB", (32, 32), "black")
            self.assertFalse(server.analyze(image, "ad_control")["accepted"])
            self.assertFalse(server.analyze(image, "external_navigation")["accepted"])
            self.assertTrue(server.analyze(image, "ad_control")["accepted"])
            self.assertTrue(server.analyze(image, "external_navigation")["accepted"])
        finally:
            vision_agent.request_vision_model = original

    def test_dispatches_gemini_provider(self):
        original = vision_agent.request_gemini
        vision_agent.request_gemini = lambda image, expected, supplied: decision()
        try:
            image = vision_agent.Image.new("RGB", (32, 32), "black")
            result = vision_agent.request_vision_model(image, "ad_control", {"provider": "gemini"})
            self.assertEqual("click_close", result["recommendedAction"])
        finally:
            vision_agent.request_gemini = original

    def test_missing_gemini_key_fails_closed(self):
        original = vision_agent.get_secret_environment_variable
        vision_agent.get_secret_environment_variable = lambda name: None
        try:
            image = vision_agent.Image.new("RGB", (32, 32), "black")
            with self.assertRaisesRegex(RuntimeError, "API key is missing"):
                vision_agent.request_gemini(
                    image,
                    "ad_control",
                    {"model": "gemini-2.5-flash", "timeoutSeconds": 1},
                )
        finally:
            vision_agent.get_secret_environment_variable = original

    def test_reads_key_from_dotenv_without_quotes(self):
        original_root = vision_agent.ROOT
        original_value = os.environ.pop("TEST_GEMINI_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                vision_agent.ROOT = Path(directory)
                (vision_agent.ROOT / ".env").write_text(
                    "# local secret\nTEST_GEMINI_KEY=test-value\n", encoding="utf-8"
                )
                self.assertEqual(
                    "test-value",
                    vision_agent.get_secret_environment_variable("TEST_GEMINI_KEY"),
                )
        finally:
            vision_agent.ROOT = original_root
            if original_value is not None:
                os.environ["TEST_GEMINI_KEY"] = original_value

    def test_gemini_3_request_uses_minimal_thinking_without_temperature(self):
        captured = {}
        original_key = vision_agent.get_secret_environment_variable
        original_urlopen = vision_agent.urllib.request.urlopen

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                envelope = {
                    "candidates": [
                        {"content": {"parts": [{"text": json.dumps(decision())}]}}
                    ]
                }
                return json.dumps(envelope).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        vision_agent.get_secret_environment_variable = lambda name: "test-key"
        vision_agent.urllib.request.urlopen = fake_urlopen
        try:
            image = vision_agent.Image.new("RGB", (320, 180), "black")
            result = vision_agent.request_gemini(
                image,
                "ad_control",
                {
                    "model": "gemini-3.5-flash-lite",
                    "endpoint": "https://example.invalid/{model}:generateContent",
                    "timeoutSeconds": 1,
                    "maximumOutputTokens": 256,
                    "thinkingLevel": "minimal",
                },
            )
            generation = captured["payload"]["generationConfig"]
            self.assertEqual("minimal", generation["thinkingConfig"]["thinkingLevel"])
            self.assertNotIn("temperature", generation)
            self.assertEqual("click_close", result["recommendedAction"])
        finally:
            vision_agent.get_secret_environment_variable = original_key
            vision_agent.urllib.request.urlopen = original_urlopen

    def test_ai_only_prompt_requires_independent_top_edge_inspection(self):
        image = vision_agent.Image.new("RGB", (320, 180), "black")
        original = vision_agent.detect_guarded_candidate
        vision_agent.detect_guarded_candidate = lambda supplied: self.fail(
            "AI-only mode must not call OpenCV candidate detection"
        )
        try:
            prompt, diagnostic = vision_agent.build_user_prompt(
                image, "ad_control_ai_only_123"
            )
            self.assertIn("independent AI-only control check", prompt)
            self.assertIn("Reward granted", prompt)
            self.assertIn("Play Store", prompt)
            self.assertIn("click_google_play", prompt)
            self.assertIn("resource counters/cards", prompt)
            self.assertIn("topElevenReturned=true", prompt)
            self.assertEqual(image.size, diagnostic.size)
        finally:
            vision_agent.detect_guarded_candidate = original

    def test_ai_only_trusts_model_close_without_edge_or_confidence_veto(self):
        raw = decision(x=0.5, y=0.7, confidence=0.2, text="Install Buy")
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "ad_control_ai_only_123"
        )
        self.assertEqual([], errors)
        self.assertEqual("click_close", normalized["recommendedAction"])

    def test_ai_only_accepts_explicit_top_eleven_header_return(self):
        raw = decision(
            action="none",
            control="none",
            x=None,
            y=None,
            confidence=0.98,
            text="tokens rests morale health cash",
        )
        raw["screenType"] = "top_eleven"
        raw["topElevenReturned"] = True
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "ad_control_ai_only_123"
        )
        self.assertEqual([], errors)
        self.assertTrue(normalized["topElevenReturned"])
        self.assertEqual("none", normalized["recommendedAction"])

    def test_ai_only_still_rejects_coordinates_outside_image(self):
        raw = decision(x=2000, y=2000, confidence=0.9)
        _, errors = vision_agent.validate_decision(
            raw,
            self.config,
            "ad_control_ai_only_123",
            image_size=(1095, 631),
        )
        self.assertIn("coordinates outside 0..1", errors)

    def test_ai_only_converts_gemini_1000_scale_coordinates(self):
        raw = decision(x=26, y=94, confidence=0.99)
        normalized, errors = vision_agent.validate_decision(
            raw,
            self.config,
            "ad_control_ai_only_123",
            image_size=(1095, 631),
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.026, normalized["control"]["x"])
        self.assertAlmostEqual(0.094, normalized["control"]["y"])

    def test_pixel_center_replaces_close_ai_coordinate_without_offset(self):
        model_decision = decision(x=0.85, y=0.105, confidence=0.99)
        candidate = {
            "found": True,
            "kind": "close",
            "x": 0.8645,
            "y": 0.0774,
            "method": "tiny-overlay",
        }
        selected = vision_agent.select_pixel_control_candidate(
            model_decision, [candidate]
        )
        self.assertIs(candidate, selected)
        self.assertEqual(0.0774, selected["y"])

    def test_ai_close_is_centered_only_near_selected_point(self):
        import cv2
        import numpy as np

        image = np.zeros((600, 1000, 3), dtype=np.uint8)
        cv2.line(image, (910, 70), (930, 90), (255, 255, 255), 3)
        cv2.line(image, (930, 70), (910, 90), (255, 255, 255), 3)
        pil_image = vision_agent.Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        model_decision = decision(x=0.920, y=0.145, confidence=0.99)

        refined, info = vision_agent.refine_ai_close_on_fresh_frame(
            pil_image, model_decision
        )

        self.assertTrue(info["ok"])
        self.assertTrue(info["applied"])
        self.assertAlmostEqual(0.920, refined["control"]["x"], places=3)
        self.assertAlmostEqual(80 / 600, refined["control"]["y"], places=3)
        self.assertEqual(0.145, model_decision["control"]["y"])

    def test_ai_close_refinement_fails_closed_without_nearby_x(self):
        blank = vision_agent.Image.new("RGB", (1000, 600), "black")
        model_decision = decision(x=0.920, y=0.145, confidence=0.99)
        refined, info = vision_agent.refine_ai_close_on_fresh_frame(
            blank, model_decision
        )
        self.assertFalse(info["ok"])
        self.assertFalse(info["applied"])
        self.assertEqual(model_decision, refined)

    def test_server_uses_exact_ai_close_when_optional_pixel_style_is_unknown(self):
        source = (ROOT / "VisionAgent.py").read_text(encoding="utf-8")
        serve_start = source.index("def serve(")
        serve = source[serve_start:]
        refinement_start = serve.index('if refinement.get("ok") and refinement.get("applied")')
        refinement_end = serve.index("if (", refinement_start + 20)
        fallback_block = serve[refinement_start:refinement_end]
        self.assertIn('fallbackToAiCoordinate', fallback_block)
        self.assertNotIn('result["accepted"] = False', fallback_block)
        self.assertNotIn('AI close X was not locally verified', fallback_block)

    def test_pixel_center_matches_google_play_control_type(self):
        model_decision = decision(
            action="click_google_play",
            control="google_play",
            x=0.88,
            y=0.14,
            confidence=0.99,
        )
        close = {"found": True, "kind": "close", "x": 0.90, "y": 0.11}
        play = {
            "found": True,
            "kind": "google_play",
            "x": 0.89,
            "y": 0.10,
        }
        selected = vision_agent.select_pixel_control_candidate(
            model_decision, [close, play]
        )
        self.assertIs(play, selected)

    def test_far_pixel_candidate_does_not_move_ai_coordinate(self):
        model_decision = decision(x=0.90, y=0.10, confidence=0.99)
        far_candidate = {
            "found": True,
            "kind": "close",
            "x": 0.65,
            "y": 0.30,
        }
        self.assertIsNone(
            vision_agent.select_pixel_control_candidate(
                model_decision, [far_candidate]
            )
        )

    def test_mourinho_prompt_uses_full_image_without_opencv_candidate(self):
        image = vision_agent.Image.new("RGB", (1091, 634), "black")
        original = vision_agent.detect_guarded_candidate
        vision_agent.detect_guarded_candidate = lambda supplied: self.fail(
            "Mourinho target mode must send the screenshot directly to AI"
        )
        try:
            prompt, supplied = vision_agent.build_user_prompt(image, "mourinho_warning")
            self.assertIn("Nivo spremnosti", prompt)
            self.assertIn("PREGLED UTAKMICE", prompt)
            self.assertIn("control.type=mourinho_warning", prompt)
            self.assertIn("recommendedAction=click_target", prompt)
            self.assertIs(image, supplied)
        finally:
            vision_agent.detect_guarded_candidate = original

    def test_accepts_ai_mourinho_target_inside_readiness_zone(self):
        normalized, errors = vision_agent.validate_decision(
            mourinho_decision(), self.config, "mourinho_warning", image_size=(1091, 634)
        )
        self.assertEqual([], errors)
        self.assertEqual("click_target", normalized["recommendedAction"])
        self.assertEqual("mourinho_warning", normalized["control"]["type"])

    def test_rejects_ai_mourinho_target_outside_readiness_zone(self):
        _, errors = vision_agent.validate_decision(
            mourinho_decision(x=0.2, y=0.2),
            self.config,
            "mourinho_warning",
            image_size=(1091, 634),
        )
        self.assertIn("Mourinho warning coordinate outside readiness-bar zone", errors)

    def test_rejects_click_target_in_other_states(self):
        _, errors = vision_agent.validate_decision(
            mourinho_decision(), self.config, "ad_control", image_size=(1091, 634)
        )
        self.assertIn("click_target is only allowed for mourinho_warning", errors)

    def test_training_prompts_require_literal_percentage_not_bar_color(self):
        image = vision_agent.Image.new("RGB", (1092, 631), "black")
        setup_prompt, setup_image = vision_agent.build_user_prompt(
            image, "training_setup_condition_123"
        )
        profile_prompt, profile_image = vision_agent.build_user_prompt(
            image, "training_profile_condition_456"
        )
        self.assertIn("literal FIT percentage", setup_prompt)
        self.assertIn("not from bar color or bar width", setup_prompt)
        self.assertIn("CONDITION: NN%", setup_prompt)
        self.assertIn("literal percentage number next to KONDICIJA", profile_prompt)
        self.assertIn("Do not estimate from the colored bar", profile_prompt)
        self.assertIs(image, setup_image)
        self.assertIs(image, profile_image)

    def test_accepts_training_player_below_30_percent(self):
        raw = decision(
            action="click_training_player",
            control="training_player",
            x=0.50,
            y=0.60,
            confidence=0.99,
            text="CONDITION: 18%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_setup_condition_1", image_size=(1092, 631)
        )
        self.assertEqual([], errors)
        self.assertEqual("click_training_player", normalized["recommendedAction"])

    def test_normalizes_gemini_0_to_1000_training_row_coordinates(self):
        raw = decision(
            action="click_training_player",
            control="training_player",
            x=487,
            y=574,
            confidence=1.0,
            text="CONDITION: 19%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_setup_condition_113020", image_size=(1092, 631)
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.487, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.574, normalized["control"]["y"], places=3)

    def test_rejects_training_player_click_at_30_percent(self):
        raw = decision(
            action="click_training_player",
            control="training_player",
            x=0.50,
            y=0.60,
            confidence=0.99,
            text="CONDITION: 30%",
        )
        raw["screenType"] = "top_eleven"
        _, errors = vision_agent.validate_decision(
            raw, self.config, "training_setup_condition_2", image_size=(1092, 631)
        )
        self.assertIn("training player click condition is not below 30%", errors)

    def test_accepts_ai_confirmation_that_all_players_are_ready(self):
        raw = decision(
            action="none", control="none", x=None, y=None, confidence=0,
            text="LOWEST_CONDITION: 58%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_setup_condition_3", image_size=(1092, 631)
        )
        self.assertEqual([], errors)
        self.assertEqual("none", normalized["recommendedAction"])

    def test_accepts_ai_profile_condition_85_percent(self):
        raw = decision(
            action="click_training_player_close", control="training_player_close",
            x=0.88, y=0.10, confidence=0.99,
            text="CONDITION: 85%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_profile_condition_4", image_size=(1092, 631)
        )
        self.assertEqual([], errors)
        self.assertEqual("CONDITION: 85%", normalized["visibleText"])
        self.assertEqual("click_training_player_close", normalized["recommendedAction"])

    def test_normalizes_gemini_profile_x_and_rejects_titlebar_x(self):
        raw = decision(
            action="click_training_player_close",
            control="training_player_close",
            x=880,
            y=100,
            confidence=0.99,
            text="CONDITION: 88%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_profile_condition_7", image_size=(1048, 719)
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.88, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.10, normalized["control"]["y"], places=3)

        raw["control"]["y"] = 20
        _, errors = vision_agent.validate_decision(
            raw, self.config, "training_profile_condition_8", image_size=(1048, 719)
        )
        self.assertIn("training player X coordinate outside profile header zone", errors)

    def test_ai_profile_below_85_targets_condition_plus(self):
        raw = decision(
            action="click_training_condition_plus",
            control="training_condition_plus",
            x=864,
            y=674,
            confidence=0.99,
            text="CONDITION: 19%",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "training_profile_condition_5", image_size=(1048, 719)
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.864, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.674, normalized["control"]["y"], places=3)

    def test_ai_profile_rejects_wrong_plus_column(self):
        raw = decision(
            action="click_training_condition_plus",
            control="training_condition_plus",
            x=0.62,
            y=0.67,
            confidence=0.99,
            text="CONDITION: 19%",
        )
        raw["screenType"] = "top_eleven"
        _, errors = vision_agent.validate_decision(
            raw, self.config, "training_profile_condition_6", image_size=(1048, 719)
        )
        self.assertIn("training condition plus coordinate outside KONDICIJA panel zone", errors)

    def test_campus_prompt_requests_building_not_percentage(self):
        image = vision_agent.Image.new("RGB", (1092, 631), "black")
        original = vision_agent.detect_guarded_candidate
        vision_agent.detect_guarded_candidate = lambda supplied: self.fail(
            "Campus building mode must send the screenshot directly to AI"
        )
        try:
            prompt, supplied = vision_agent.build_user_prompt(
                image, "campus_incomplete_building_object_1_123"
            )
            self.assertIn("WELL INSIDE", prompt)
            self.assertIn("Do NOT return the percentage badge", prompt)
            self.assertIn("road, generic grass", prompt)
            self.assertIn("strictly below 100%", prompt)
            self.assertIn("farthest LEFT", prompt)
            self.assertIn("click_campus_building", prompt)
            self.assertIn("TARGET: <facility name>; PERCENT: <NN%>", prompt)
            self.assertIs(image, supplied)
        finally:
            vision_agent.detect_guarded_candidate = original

    def test_campus_tool_prompt_uses_ai_and_accepts_gemini_coordinates(self):
        image = vision_agent.Image.new("RGB", (1092, 631), "black")
        prompt, supplied = vision_agent.build_user_prompt(
            image, "campus_tool_icon_123"
        )
        self.assertIn("crossed wrench/screwdriver", prompt)
        self.assertIn("click_campus_tool", prompt)
        self.assertIn("Do not select", prompt)
        self.assertIs(image, supplied)

        raw = decision(
            action="click_campus_tool",
            control="campus_tool",
            x=55,
            y=300,
            confidence=0.99,
            text="crossed tools",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "campus_tool_icon_123", image_size=(1092, 631)
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.055, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.300, normalized["control"]["y"], places=3)

    def test_campus_tool_rejects_coordinate_outside_left_tool_zone(self):
        raw = decision(
            action="click_campus_tool",
            control="campus_tool",
            x=0.50,
            y=0.30,
            confidence=0.99,
            text="crossed tools",
        )
        raw["screenType"] = "top_eleven"
        _, errors = vision_agent.validate_decision(
            raw, self.config, "campus_tool_icon_456", image_size=(1092, 631)
        )
        self.assertIn("Campus tool coordinate outside left Campus tool zone", errors)

    def test_connection_popup_prompt_and_confirmation_button(self):
        image = vision_agent.Image.new("RGB", (1050, 650), "black")
        prompt, supplied = vision_agent.build_user_prompt(
            image, "connection_interrupted_popup_123"
        )
        self.assertIn("VEZA JE PREKINUTA", prompt)
        self.assertIn("white checkmark", prompt)
        self.assertIn("click_connection_confirm", prompt)
        self.assertIs(image, supplied)

        raw = decision(
            action="click_connection_confirm",
            control="connection_confirm",
            x=500,
            y=680,
            confidence=0.99,
            text="VEZA JE PREKINUTA",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "connection_interrupted_popup_123",
            image_size=(1050, 650),
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.5, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.68, normalized["control"]["y"], places=3)

    def test_connection_popup_rejects_green_button_outside_modal_zone(self):
        raw = decision(
            action="click_connection_confirm",
            control="connection_confirm",
            x=0.90,
            y=0.70,
            confidence=0.99,
            text="VEZA JE PREKINUTA",
        )
        raw["screenType"] = "top_eleven"
        _, errors = vision_agent.validate_decision(
            raw, self.config, "connection_interrupted_popup_456",
            image_size=(1050, 650),
        )
        self.assertIn("connection confirmation coordinate outside modal button zone", errors)

    def test_incidental_top_eleven_popup_prompt_and_close(self):
        image = vision_agent.Image.new("RGB", (1050, 650), "black")
        prompt, supplied = vision_agent.build_user_prompt(
            image, "incidental_top_eleven_popup_123"
        )
        self.assertIn("EKSPERTSKA KONDICIJA", prompt)
        self.assertIn("click_incidental_popup_close", prompt)
        self.assertIn("Never select the BlueStacks title-bar X", prompt)
        self.assertIs(image, supplied)

        raw = decision(
            action="click_incidental_popup_close",
            control="incidental_popup_close",
            x=780,
            y=230,
            confidence=0.99,
            text="EKSPERTSKA KONDICIJA purchase offer",
        )
        raw["screenType"] = "top_eleven"
        normalized, errors = vision_agent.validate_decision(
            raw, self.config, "incidental_top_eleven_popup_123",
            image_size=(1050, 650),
        )
        self.assertEqual([], errors)
        self.assertAlmostEqual(0.78, normalized["control"]["x"], places=3)
        self.assertAlmostEqual(0.23, normalized["control"]["y"], places=3)

    def test_incidental_popup_rejects_bluestacks_titlebar_x(self):
        raw = decision(
            action="click_incidental_popup_close",
            control="incidental_popup_close",
            x=0.93,
            y=0.03,
            confidence=0.99,
            text="offer",
        )
        raw["screenType"] = "top_eleven"
        _, errors = vision_agent.validate_decision(
            raw, self.config, "incidental_top_eleven_popup_456",
            image_size=(1050, 650),
        )
        self.assertIn("incidental popup close coordinate outside modal header zone", errors)

    def test_campus_target_resolves_to_canonical_safe_facility(self):
        target = vision_agent.resolve_campus_target(
            "TARGET: PRODAJA HRANE; PERCENT: 90%"
        )
        self.assertIsNotNone(target)
        self.assertEqual("prodaja_hrane", target[0])
        self.assertEqual((0.275, 0.745), target[1])

    def test_campus_grounding_replaces_ai_label_point_with_safe_building_point(self):
        reference = vision_agent.Image.open(
            vision_agent.CAMPUS_REFERENCE_PATH
        ).convert("RGB")
        result = vision_agent.ground_campus_click_on_fresh_frame(
            reference,
            campus_decision(
                x=0.202,
                y=0.801,
                text="TARGET: PRODAJA HRANE; PERCENT: 90%",
            ),
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual("prodaja_hrane", result["target"])
        self.assertAlmostEqual(0.275, result["x"], delta=0.005)
        self.assertAlmostEqual(0.745, result["y"], delta=0.005)
        self.assertNotAlmostEqual(0.202, result["x"], delta=0.02)

    def test_campus_grounding_tracks_projective_camera_motion(self):
        import cv2
        import numpy as np

        reference = cv2.imread(str(vision_agent.CAMPUS_REFERENCE_PATH))
        height, width = reference.shape[:2]
        transform = np.array(
            [
                [1.0, 0.08, -0.04 * width],
                [-0.02, 1.02, 0.01 * height],
                [0.00012, -0.00008, 1.0],
            ],
            dtype=np.float64,
        )
        moved = cv2.warpPerspective(
            reference,
            transform,
            (width, height),
            borderMode=cv2.BORDER_REFLECT,
        )
        moved_image = vision_agent.Image.fromarray(
            cv2.cvtColor(moved, cv2.COLOR_BGR2RGB)
        )
        result = vision_agent.ground_campus_click_on_fresh_frame(
            moved_image,
            campus_decision(text="TARGET: STADION; PERCENT: 60%"),
        )
        canonical = np.array(
            [[[0.485 * width, 0.635 * height]]], dtype=np.float32
        )
        expected = cv2.perspectiveTransform(canonical, transform)[0, 0]
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(expected[0] / width, result["x"], delta=0.012)
        self.assertAlmostEqual(expected[1] / height, result["y"], delta=0.012)
        self.assertGreaterEqual(result["inliers"], 25)

    def test_campus_grounding_fails_closed_on_unrelated_frame(self):
        blank = vision_agent.Image.new("RGB", (1092, 631), "black")
        result = vision_agent.ground_campus_click_on_fresh_frame(
            blank,
            campus_decision(text="TARGET: STADION; PERCENT: 60%"),
        )
        self.assertFalse(result["ok"])

    def test_campus_click_is_accepted_once_and_verified_after_click(self):
        config = {
            "minimumConfidence": 0.85,
            "requiredAgreementCount": 1,
            "coordinateTolerance": 0.035,
            "saveUnknownScreenshots": False,
        }
        server = vision_agent.VisionServer(config)
        original = vision_agent.request_vision_model
        vision_agent.request_vision_model = lambda image, expected, supplied: campus_decision()
        try:
            image = vision_agent.Image.new("RGB", (1092, 631), "black")
            first_state = "campus_incomplete_building_object_1_123"
            first = server.analyze(image, first_state)
            fresh_retry = server.analyze(
                image, "campus_incomplete_building_object_1_retry_2_avoid_500_700_456"
            )

            self.assertTrue(first["accepted"])
            self.assertEqual(1, first["stableCount"])
            self.assertEqual(1, first["requiredStableCount"])
            self.assertTrue(fresh_retry["accepted"])
            self.assertEqual(1, fresh_retry["stableCount"])
        finally:
            vision_agent.request_vision_model = original

    def test_campus_none_requires_two_fresh_confirmations(self):
        config = {
            "minimumConfidence": 0.85,
            "requiredAgreementCount": 1,
            "coordinateTolerance": 0.035,
            "saveUnknownScreenshots": False,
        }
        server = vision_agent.VisionServer(config)
        original = vision_agent.request_vision_model
        vision_agent.request_vision_model = (
            lambda image, expected, supplied: campus_none_decision()
        )
        try:
            image = vision_agent.Image.new("RGB", (1092, 631), "black")
            state = "campus_incomplete_building_object_1_none"
            first = server.analyze(image, state)
            second = server.analyze(image, state)
            self.assertFalse(first["accepted"])
            self.assertEqual(2, first["requiredStableCount"])
            self.assertTrue(second["accepted"])
        finally:
            vision_agent.request_vision_model = original

    def test_campus_click_requires_parsable_percentage_below_100(self):
        for text, expected_error in (
            ("STADION 60%", "Campus click has no parsable TARGET/PERCENT text"),
            (
                "TARGET: STADION; PERCENT: 100%",
                "Campus click target is not below 100%",
            ),
        ):
            with self.subTest(text=text):
                _, errors = vision_agent.validate_decision(
                    campus_decision(text=text),
                    self.config,
                    "campus_incomplete_building",
                    image_size=(1092, 631),
                )
                self.assertIn(expected_error, errors)

        _, errors = vision_agent.validate_decision(
            campus_decision(text="TARGET Parking PERCENT 90%"),
            self.config,
            "campus_incomplete_building",
            image_size=(1092, 631),
        )
        self.assertEqual([], errors)

    def test_campus_retry_prompt_marks_every_failed_coordinate(self):
        image = vision_agent.Image.new("RGB", (1092, 631), "black")
        prompt, supplied = vision_agent.build_user_prompt(
            image,
            "campus_incomplete_building_object_2_retry_3_avoid_430_630_avoid_500_700_789",
        )
        self.assertIn("RED CROSSED CIRCLES", prompt)
        self.assertIn("(0.430, 0.630), (0.500, 0.700)", prompt)
        self.assertIsNot(image, supplied)
        self.assertGreater(supplied.getpixel((round(0.43 * 1092), round(0.63 * 631)))[0], 200)

    def test_accepts_ai_campus_building_inside_object_zone(self):
        normalized, errors = vision_agent.validate_decision(
            campus_decision(),
            self.config,
            "campus_incomplete_building",
            image_size=(1092, 631),
        )
        self.assertEqual([], errors)
        self.assertEqual("click_campus_building", normalized["recommendedAction"])
        self.assertEqual("campus_building", normalized["control"]["type"])

    def test_accepts_ai_campus_building_for_unique_retry_state(self):
        normalized, errors = vision_agent.validate_decision(
            campus_decision(),
            self.config,
            "campus_incomplete_building_object_2_retry_3_avoid_700_700_789",
            image_size=(1092, 631),
        )
        self.assertEqual([], errors)
        self.assertEqual("click_campus_building", normalized["recommendedAction"])

    def test_campus_retry_rejects_the_previously_failed_coordinate(self):
        retry_state = "campus_incomplete_building_object_2_retry_2_avoid_430_630_789"
        _, errors = vision_agent.validate_decision(
            campus_decision(x=0.43, y=0.63),
            self.config,
            retry_state,
            image_size=(1092, 631),
        )
        self.assertIn("Campus retry repeated a previously failed coordinate", errors)

        normalized, errors = vision_agent.validate_decision(
            campus_decision(x=0.48, y=0.63),
            self.config,
            retry_state,
            image_size=(1092, 631),
        )
        self.assertEqual([], errors)
        self.assertEqual(0.48, normalized["control"]["x"])

        _, errors = vision_agent.validate_decision(
            campus_decision(x=0.50, y=0.70),
            self.config,
            "campus_incomplete_building_object_2_retry_3_avoid_430_630_avoid_500_700_789",
            image_size=(1092, 631),
        )
        self.assertIn("Campus retry repeated a previously failed coordinate", errors)

    def test_rejects_ai_campus_building_outside_object_zone(self):
        _, errors = vision_agent.validate_decision(
            campus_decision(x=0.96, y=0.1),
            self.config,
            "campus_incomplete_building",
            image_size=(1092, 631),
        )
        self.assertIn("Campus building coordinate outside campus object zone", errors)

    def test_rejects_campus_building_action_in_other_states(self):
        _, errors = vision_agent.validate_decision(
            campus_decision(), self.config, "ad_control", image_size=(1092, 631)
        )
        self.assertIn(
            "click_campus_building is only allowed for campus_incomplete_building",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
