import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from test_vision_agent import vision_agent as vision, decision
from test_external_navigation_recovery import function_source, run_powershell


class AdCornerViewTests(unittest.TestCase):
    def setUp(self):
        self.image = vision.Image.new('RGB', (1067, 615), (255, 0, 255))
        self.image.paste((0, 255, 0), (0, 0, 1067, 40))
        self.image.paste((0, 255, 255), (1025, 40, 1067, 615))
        self.image.paste((255, 0, 0), (0, 40, 226, 241))
        self.image.paste((0, 0, 255), (799, 40, 1025, 241))
        self.view, self.regions = vision.build_ad_corner_image(self.image, {})

    def panel_point(self, side, x, y):
        sx1, sy1, sx2, sy2 = self.regions[side]['source']
        left, top, right, bottom = self.regions[side]['panel']
        return ((left+(x-sx1)*(right-left)/(sx2-sx1))/self.view.width,
                (top+(y-sy1)*(bottom-top)/(sy2-sy1))/self.view.height)

    def test_image_contains_only_two_game_corners_and_labels(self):
        colors = {color for count, color in self.view.getcolors(self.view.width*self.view.height)}
        for hidden in ((255, 0, 255), (0, 255, 0), (0, 255, 255)):
            self.assertNotIn(hidden, colors)
        self.assertEqual((920, 426), self.view.size)
        self.assertIn((255, 0, 0), colors)
        self.assertIn((0, 0, 255), colors)

    def test_left_and_right_controls_map_to_original_window(self):
        for side, original in ((0, (30, 71)), (1, (1000, 71))):
            for scale in (1, 1000):
                x, y = self.panel_point(side, *original)
                raw = decision(x=x*scale, y=y*scale)
                mapped = vision.map_ad_corner_decision(raw, self.view.size, self.image.size, self.regions)
                self.assertAlmostEqual(original[0]/self.image.width, mapped['control']['x'])
                self.assertAlmostEqual(original[1]/self.image.height, mapped['control']['y'])
                self.assertEqual(x*scale, raw['control']['x'])

    def test_labels_separator_and_invalid_coordinates_are_rejected(self):
        gap_x = (self.regions[0]['panel'][2]+8)/self.view.width
        for x, y in ((.1, .01), (gap_x, .5), (1, 1), (-.1, .5), (math.nan, .5), (.5, math.inf)):
            raw = decision(x=x, y=y)
            mapped = vision.map_ad_corner_decision(raw, self.view.size, self.image.size, self.regions)
            self.assertEqual(-1, mapped['control']['x'])

    def test_partial_corners_cannot_authorize_game_return_or_back(self):
        raw = decision(action='none', control='none', x=None, y=None)
        raw['screenType'] = 'top_eleven'
        raw['topElevenReturned'] = True
        mapped = vision.map_ad_corner_decision(raw, self.view.size, self.image.size, self.regions)
        self.assertFalse(mapped['topElevenReturned'])
        self.assertEqual('unknown', mapped['screenType'])
        back = decision(action='send_back', control='back', x=None, y=None)
        self.assertEqual('invalid_corner_action', vision.map_ad_corner_decision(
            back, self.view.size, self.image.size, self.regions)['recommendedAction'])

    def test_both_providers_receive_only_corners_and_return_mapped_coordinates(self):
        for provider in ('gemini', 'ollama'):
            def respond(image, state, config):
                self.assertEqual(self.view.tobytes(), image.tobytes())
                self.assertTrue(state.endswith('__ad_corners'))
                x, y = self.panel_point(1, 1000, 71)
                return decision(x=x, y=y)
            with patch.object(vision, 'request_'+provider, side_effect=respond):
                mapped = vision.request_vision_model(self.image, 'ad_control_ai_only_123', {'provider': provider})
            self.assertAlmostEqual(1000/1067, mapped['control']['x'])
            self.assertAlmostEqual(71/615, mapped['control']['y'])

    def test_other_screen_checks_keep_full_image(self):
        for state in ('external_navigation_1', 'campus_incomplete_building_1', 'training_profile_condition_1'):
            def respond(image, expected, config):
                self.assertIs(self.image, image)
                self.assertEqual(state, expected)
                return decision(action='none', control='none', x=None, y=None)
            with patch.object(vision, 'request_gemini', side_effect=respond):
                vision.request_vision_model(self.image, state, {'provider': 'gemini'})

    def test_corner_prompts_allow_named_store_controls_and_forbid_install(self):
        prompt, supplied = vision.build_user_prompt(self.view, 'ad_control_ai_only_123__ad_corners')
        self.assertIs(supplied, self.view)
        self.assertEqual(vision.AD_CORNERS_SYSTEM_PROMPT,
                         vision.system_prompt_for_expected_state('ad_control_ai_only_123__ad_corners'))
        for text in ('Open Store', 'Google Play', 'Play Store', 'click_google_play', 'Install/Get'):
            self.assertIn(text, prompt)

    def test_current_dpi_viewport_insets_are_used(self):
        view, regions = vision.build_ad_corner_image(self.image, {'adCornerTopInsetPx': 60, 'adCornerRightInsetPx': 63})
        self.assertEqual(60, regions[0]['source'][1])
        self.assertEqual(1004, regions[1]['source'][2])
        self.assertGreater(view.height, 0)


class AdStoreTextTests(unittest.TestCase):
    def test_tiny_end_card_x_reaches_verified_close_response(self):
        image = vision.Image.open(Path(__file__).with_name(
            'kingshot-tiny-close-20261008.png'))
        raw = decision(x=.857, y=.073)
        refined, info = vision.refine_ai_close_on_fresh_frame(image, raw)
        self.assertTrue(info['ok'])
        self.assertTrue(info['applied'])
        self.assertEqual('click_close', refined['recommendedAction'])
        self.assertAlmostEqual(311/361, refined['control']['x'], delta=.006)
        self.assertAlmostEqual(47.5/616, refined['control']['y'], delta=.006)

    def test_logged_wake_store_coordinate_is_refined_to_actual_disclosure(self):
        image = vision.Image.open(Path(__file__).with_name(
            'kingshot-store-badge-20261008.png'))
        for ai_x, ai_y in ((.154, .095), (.148, .096)):
            original = decision(action='click_google_play', control='google_play',
                                x=ai_x, y=ai_y, confidence=.95)
            refined, info = vision.refine_decision_control_center(image, original)
            self.assertTrue(info['applied'])
            self.assertEqual('google_play', info['kind'])
            self.assertTrue(10 < refined['control']['x']*361 < 58)
            self.assertTrue(40 < refined['control']['y']*616 < 54)
            self.assertEqual(ai_x, original['control']['x'])
            self.assertEqual(ai_y, original['control']['y'])

    def test_only_confirmed_store_text_can_release_the_selected_candidate(self):
        code = function_source('Confirm-AdStoreTextCandidate') + r'''
$ErrorActionPreference='Stop'
function Add-Log {}
function Read-LocalGreenOfferText { return $script:label }
$answers=@()
foreach ($label in @('Open Store','Google Play','Play Store','Visit Google Play','Install','Open','Open Store Install','Unknown')) {
 $script:label=$label
 $r=[PSCustomObject]@{accepted=$false; googlePlayTextCheck='crop'; errors=@('Google Play badge was not locally verified'); decision=[PSCustomObject]@{recommendedAction='click_google_play';control=[PSCustomObject]@{x=.10;y=.11}}}
 $r=Confirm-AdStoreTextCandidate $r
 $answers += [bool]$r.accepted
}
ConvertTo-Json -Compress $answers
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([True, True, True, True, False, False, False, False], json.loads(result.stdout))

    def test_text_cannot_override_another_validation_failure(self):
        code = function_source('Confirm-AdStoreTextCandidate') + r'''
$ErrorActionPreference='Stop'
function Read-LocalGreenOfferText { throw 'OCR must not override other rejection' }
$r=[PSCustomObject]@{accepted=$false;googlePlayTextCheck='crop';errors=@('coordinates outside 0..1','Google Play badge was not locally verified');decision=[PSCustomObject]@{recommendedAction='click_google_play'}}
$r=Confirm-AdStoreTextCandidate $r
if ($r.accepted) {throw 'invalid candidate accepted'}
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
