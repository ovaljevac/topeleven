import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_vision_agent import vision_agent as vision, decision
from test_training_player_flow import x_detector as detector
from test_external_navigation_recovery import function_source, run_powershell

ROOT = Path(__file__).resolve().parents[1]


class RemainingFlowFixes(unittest.TestCase):
    def run_ps(self, names, code):
        result = run_powershell("$ErrorActionPreference='Stop'\nAdd-Type -AssemblyName System.Drawing\n" +
                                '\n'.join(function_source(name) for name in names) + '\n' + code)
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        return result.stdout.strip()

    def test_preflight_preserves_full_frame_game_and_external_back(self):
        image = vision.Image.new('RGB', (1067, 615), 'red')
        for provider in ('gemini', 'ollama'):
            for screen, action in (('top_eleven', 'none'), ('google_play_store', 'send_back')):
                raw = decision(action=action, control='none', x=None, y=None)
                raw['screenType'] = screen
                raw['topElevenReturned'] = screen == 'top_eleven'
                with patch.object(vision, 'request_' + provider, return_value=raw) as request:
                    result = vision.request_vision_model(image, 'ad_control_ai_only_preflight_123', {'provider': provider})
                self.assertIs(image, request.call_args.args[0])
                self.assertEqual('ad_control_ai_only_preflight_123', request.call_args.args[1])
                self.assertEqual(raw, result)
                self.assertFalse(vision.uses_ad_corner_view('ad_control_ai_only_preflight_123'))
                self.assertTrue(vision.uses_ad_corner_view('ad_control_ai_only_followup_123'))

    def test_profile_return_requires_two_matching_verified_local_frames(self):
        for state, second_state, verified, expected in (
            ('player_detail', 'player_detail', True, True),
            ('condition_modal', 'condition_modal', True, True),
            ('player_detail', 'unknown', True, False),
            ('player_detail', 'player_detail', False, False),
        ):
            code = r'''
function Get-TVFlowSnapshot {return @{state='unknown'}}
function Test-StoreReturnVisualProof {return $false}
function Test-GreenGameReturned {return $false}
function Wait-Agent {}
function Get-TrainingPlayerFlowSnapshot {
 $script:reads++
 $state=if($script:reads -eq 1){'FIRST'}else{'SECOND'}
 return @{state=$state;profileVerified=VERIFIED;modalClose=@{x=.6;y=.88}}
}
$script:reads=0
Test-TopElevenReturnedAfterAd ([IntPtr]1) | ConvertTo-Json -Compress
'''.replace('FIRST', state).replace('SECOND', second_state).replace('VERIFIED', '$true' if verified else '$false')
            self.assertEqual(expected, json.loads(self.run_ps(['Test-TopElevenReturnedAfterAd'], code)))

    def test_real_game_detail_returns_without_ai(self):
        self.run_ps(['Test-TopElevenReturnedAfterAd'], r'''
function Get-TVFlowSnapshot {return @{state='unknown'}}
function Test-StoreReturnVisualProof {return $false}
function Test-GreenGameReturned {return $true}
function Get-TrainingPlayerFlowSnapshot {throw 'already returned'}
if (-not (Test-TopElevenReturnedAfterAd ([IntPtr]1))) {throw 'Campus header ignored'}
''')

    def test_background_change_cannot_move_campus_cards(self):
        image = detector.load_image(ROOT / 'tests/campus-stadium-strip-20261008.png')
        changed = image.copy()
        changed[455:470, 21:522] = detector.np.clip(changed[455:470, 21:522].astype(int) + 40, 0, 255)
        before, after = detector._campus_object_strip(image), detector._campus_object_strip(changed)
        self.assertEqual(before['cards'], after['cards'])
        self.assertGreater(detector.np.mean(detector.np.abs(
            detector.np.asarray(before['fingerprint']) - detector.np.asarray(after['fingerprint']))), 3)
        moved = copy.deepcopy(after)
        for card in moved['cards']:
            card['x'] += .04
        swapped = copy.deepcopy(after)
        swapped['cards'][0]['identity'] = before['cards'][1]['identity']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cards.json'
            path.write_text(json.dumps({'before': before, 'after': [after, moved, swapped]}))
            code = "$data=Get-Content -LiteralPath '" + str(path).replace("'", "''") + "' -Raw | ConvertFrom-Json\n"
            code += "$answers=@($data.after | ForEach-Object {Test-CampusObjectCardsMoved $data.before $_})\nConvertTo-Json -Compress $answers"
            self.assertEqual([False, True, True], json.loads(self.run_ps(['Test-CampusObjectCardsMoved'], code)))

    def test_invalid_campus_card_identity_cannot_prove_movement(self):
        self.run_ps(['Test-CampusObjectCardsMoved'], r'''
$b=@{verified=$true;cards=@(@{identity=@()},@{identity=@()})}
try {Test-CampusObjectCardsMoved $b $b;throw 'accepted invalid identity'}
catch {if ($_.Exception.Message -ne 'Kampus kartica nema potvrdenu sliku.') {throw}}
'checked'
''')

    def test_game_header_and_green_plus_survive_dpi_scaling(self):
        image = detector.load_image(ROOT / 'tests/campus-stadium-strip-20261008.png')
        native = detector.detect_top_resource_cards(image)
        for scale in (1.25, 1.5, 2):
            with self.subTest(scale=scale):
                header = detector.detect_top_resource_cards(detector.cv2.resize(image, None, fx=scale, fy=scale))
                self.assertTrue(header.get('gameHeaderVerified'))
                self.assertAlmostEqual(native['greenPlus']['x'], header['greenPlus']['x'], delta=.003)
                self.assertAlmostEqual(native['greenPlus']['y'], header['greenPlus']['y'], delta=.003)

    def test_scaled_playable_ad_cannot_become_game_header(self):
        image = detector.load_image(ROOT / 'tests/kingshot-store-badge-20261008.png')
        for scale in (1.5, 2):
            header = detector.detect_top_resource_cards(detector.cv2.resize(image, None, fx=scale, fy=scale))
            self.assertFalse(header.get('gameHeaderVerified', False))

    def test_back_checks_returned_game_before_forced_ai(self):
        self.run_ps(['Restore-AdFromGooglePlay'], r'''
$script:GreenLocalFlowActive=$true
$script:ready=$false
$script:ExternalNavigationBackAttempts=6
function Test-GreenGameReturned {return $script:ready}
function Test-AiExternalNavigationVisible {param($Handle,$Started,[switch]$ForceRefresh);if($ForceRefresh){throw 'AI after game return'};return $true}
function Get-AdNavigationFingerprint {return @(0)*576}
function Set-Status {}
function Send-BlueStacksBack {$script:ready=$true}
function Wait-Agent {}
function Add-Log {}
if (-not (Restore-AdFromGooglePlay ([IntPtr]1) (Get-Date))) {throw 'Back not handled'}
if (-not $script:ready) {throw 'game not returned'}
if ($script:ExternalBackNoProgress -ne 0) {throw 'successful Back counted as stalled'}
''')


class FreshSkipTests(unittest.TestCase):
    def frame(self):
        image = detector.np.full((600, 1000, 3), 35, detector.np.uint8)
        detector.cv2.putText(image, 'Skip', (908, 75), detector.cv2.FONT_HERSHEY_SIMPLEX,
                            .55, (255, 255, 255), 1, detector.cv2.LINE_AA)
        return image

    def test_text_skip_requires_literal_ocr_and_cannot_use_image_similarity(self):
        before = self.frame()
        control = {'x': .93, 'y': .115}
        template = {'image': 'previous static patch'}
        fresh = detector.np.full_like(before, 35)
        fresh[:, 6:] = before[:, :-6]
        found = detector.refine_skip_control_near_point(fresh, control, template)
        self.assertFalse(found['found'])
        self.assertIsNotNone(found['skipTextCheck'])
        vanished = detector.np.full_like(before, 35)
        self.assertFalse(detector.refine_skip_control_near_point(vanished, control, template)['found'])
        resized = detector.cv2.resize(before, (1500, 900))
        self.assertFalse(detector.refine_skip_control_near_point(resized, control, template)['found'])

    def test_provider_latency_cannot_keep_disappeared_skip_accepted(self):
        original = self.frame()
        fresh = detector.np.full_like(original, 35)
        raw = decision(action='click_skip', control='skip', x=.93, y=.115)
        _, evidence = vision.refine_ai_skip_on_fresh_frame(vision.Image.fromarray(original), vision.Image.fromarray(fresh), raw)
        self.assertFalse(evidence['applied'])
        _, evidence = vision.refine_ai_skip_on_fresh_frame(vision.Image.fromarray(original), vision.Image.fromarray(original), raw)
        self.assertFalse(evidence['applied'])
        self.assertIsNotNone(evidence['textCheck'])

    def test_actual_click_rechecks_skip_and_uses_fresh_coordinate(self):
        for found in (True, False):
            code = r'''
$script:DryRun=$true
$script:logs=@()
function Test-Cancelled {}
function Set-BlueStacksWindowForeground {return $true}
function Start-XDetector {}
function Get-WindowRectangle {return @{Left=100;Top=100;Right=1100;Bottom=700}}
function Set-AgentPendingAction {}
function Add-Log {param($Text);$script:logs+=$Text}
function Invoke-VisionAnalysis {throw 'Skip pre-click must stay local'}
$script:XDetectorProcess=@{StandardInput=(New-Object System.IO.StringWriter)}
function Read-AgentProcessLine {return '{"found":FOUND,"kind":"skip","x":0.9,"y":0.1}'}
Click-Relative ([IntPtr]1) .93 .115 'Skip - test'
ConvertTo-Json -Compress @($script:logs)
'''.replace('FOUND', str(found).lower())
            result = run_powershell("$ErrorActionPreference='Stop'\n" +
                function_source('Confirm-AdSkipImmediatelyBeforeClick') + '\n' + function_source('Click-Relative') + code)
            self.assertEqual(0, result.returncode, result.stderr)
            logs = json.loads(result.stdout)
            if found:
                self.assertIn('DRY RUN klik: Skip - test (1000, 160)', logs)
            else:
                self.assertFalse(any('DRY RUN' in log for log in logs))

    def test_verified_ai_skip_is_ready_with_local_type_proof(self):
        code = function_source('Test-AiOnlyAdControlReady') + r'''
$ErrorActionPreference='Stop'
function Add-Log {}
function Invoke-VisionAnalysis {return @{
 accepted=$true
 decision=@{screenType='ad';topElevenReturned=$false;recommendedAction='click_skip';control=@{x=.93;y=.115;confidence=.95}}
 skipRefinement=@{applied=$true;method='local-skip-text-ocr'}
}}
if (-not (Test-AiOnlyAdControlReady ([IntPtr]1) 'ad_control_ai_only_test')) {throw 'verified Skip rejected'}
if (-not $script:DetectedAdCloseLocallyVerified) {throw 'local type proof lost'}
'checked'
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
