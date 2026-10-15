import json
import unittest
from pathlib import Path

from test_training_player_flow import x_detector as detector
from test_external_navigation_recovery import function_source, run_powershell, SCRIPT

ROOT = Path(__file__).resolve().parents[1]


class WakeStoreTimingTests(unittest.TestCase):
    def frame(self):
        return detector.load_image(ROOT / 'tests/kingshot-wake-store-20261008.png')

    def test_logged_point_is_inside_actual_disclosure_and_scales_correctly(self):
        for scale in (1, 1.5, 2):
            image = detector.cv2.resize(self.frame(), None, fx=scale, fy=scale)
            badge = detector.run_detector(image, mode='wake_store_badge')
            self.assertTrue(badge['found'], badge)
            self.assertEqual('google_play', badge['kind'])
            self.assertAlmostEqual(.094, badge['x'], delta=.006)
            self.assertAlmostEqual(.074, badge['y'], delta=.003)
            proof = detector.run_detector(image, mode='google_play_control',
                                          skip_control={'x': .094, 'y': .074})
            self.assertTrue(proof['found'], proof)

    def test_fixed_lettering_also_recognizes_other_actual_kingshot_frames(self):
        for filename in ('kingshot-store-badge', 'kingshot-false-skip'):
            image = detector.load_image(ROOT / f'tests/{filename}-20261008.png')
            self.assertTrue(detector.detect_verified_top_left_store_badge(image)['found'])

    def test_missing_disclosure_logo_blank_and_close_do_not_authorize_click(self):
        image = self.frame()
        image[34:61, :110] = (110, 110, 110)
        tiny_close = detector.load_image(ROOT / 'tests/kingshot-tiny-close-20261008.png')
        for frame in (image, tiny_close, detector.np.full_like(image, 35)):
            self.assertFalse(detector.run_detector(frame, mode='wake_store_badge')['found'])
            self.assertFalse(detector.run_detector(frame, mode='google_play_control',
                             skip_control={'x': .094, 'y': .074})['found'])

    def test_store_proof_cannot_jump_to_disclosure_from_logo_or_far_point(self):
        for control in ({'x': .118, 'y': .15}, {'x': .30, 'y': .074},
                        {'x': -1, 'y': .074}):
            proof = detector.refine_google_play_control_near_point(self.frame(), control)
            self.assertFalse(proof['found'])

    def test_preclick_cancel_prevents_dispatch_when_badge_disappears(self):
        code = '\n'.join(function_source(name) for name in (
            'Confirm-AdGooglePlayImmediatelyBeforeClick', 'Click-Relative')) + r'''
$ErrorActionPreference='Stop'
$script:DryRun=$true
function Test-Cancelled {}
function Set-BlueStacksWindowForeground {return $true}
function Get-LocalAdStoreSnapshot {return @{found=$false}}
function Set-AgentPendingAction {throw 'stale click dispatched'}
function Add-Log {param($Text);if($Text -like '*DRY RUN*'){throw 'stale click executed'}}
Click-Relative ([IntPtr]1) .094 .074 'Google Play dugme - AI-only'
if($null -ne $script:DetectedAdCloseX){throw 'stale coordinate survived'}
'checked'
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)

    def run_wake(self, found):
        code = '\n'.join(function_source(name) for name in (
            'Invoke-AdWakeStoreProbe', 'Confirm-AdGooglePlayImmediatelyBeforeClick',
            'Click-Relative')) + r'''
$ErrorActionPreference='Stop'
$script:DryRun=$true
$script:Clicks=0
$script:Reads=0
$script:Waits=0
function Test-Cancelled {}
function Set-BlueStacksWindowForeground {return $true}
function Test-AiOnlyAdControlReady {throw 'wake badge waited for AI'}
function Wait-Agent {param($Ms);$script:Waits+=$Ms}
function Get-LocalAdStoreSnapshot {
 $script:Reads++
 return @{found=FOUND;kind='google_play';x=.0958;y=.074}
}
function Get-WindowRectangle {return @{Left=710;Top=172;Right=1071;Bottom=788}}
function Set-AgentPendingAction {$script:Clicks++}
function Add-Log {}
$clicked=Invoke-AdWakeStoreProbe ([IntPtr]1)
@{clicked=$clicked;clicks=$script:Clicks;reads=$script:Reads;waits=$script:Waits} | ConvertTo-Json -Compress
'''
        code = code.replace('FOUND', '$true' if found else '$false')
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_wake_dispatches_verified_badge_without_ai_delay(self):
        result = self.run_wake(True)
        self.assertTrue(result['clicked'])
        self.assertEqual(1, result['clicks'])
        self.assertEqual(3, result['reads'])
        self.assertEqual(260, result['waits'])

    def test_wake_without_badge_never_dispatches_click(self):
        result = self.run_wake(False)
        self.assertFalse(result['clicked'])
        self.assertEqual(0, result['clicks'])
        self.assertEqual(3, result['reads'])
        self.assertEqual(680, result['waits'])

    def test_all_wake_flows_probe_local_badge_before_ai_capture_delay(self):
        for wake_name in ('"reklama za $PlayerLabel - probudi skrivenu kontrolu"',
                          '"$flowLabel reklama - probudi skrivenu kontrolu"',
                          "'reklama - probudi skrivenu kontrolu'"):
            branch = SCRIPT[SCRIPT.index(wake_name):]
            self.assertLess(branch.index('Invoke-AdWakeStoreProbe'),
                            branch.index('Wait-Agent $script:PortraitAdWakeCaptureDelayMs'))

    def test_store_ocr_keeps_literal_label_and_fresh_word_center(self):
        code = function_source('Get-AdStoreTextProof') + r'''
$ErrorActionPreference='Stop'
function Add-Log {}
function Read-LocalGreenOfferText {
 return @{Text=$script:label;Words=@([PSCustomObject]@{X=4;Y=4;Width=80;Height=32})}
}
$crop=@{image='crop';scale=4;sourceBox=@(900,60,960,90);windowSize=@(1000,600);x=.911;y=.1083}
$answers=@()
foreach($label in @('Google Play','Open Store','Play Store','Kingshot','Install','Get','Skip','Open Store Install')) {
 $script:label=$label
 $proof=Get-AdStoreTextProof $crop
 $answers+=($null -ne $proof)
 if($null -ne $proof -and [Math]::Abs($proof.x-.911) -gt .001){throw 'wrong word center'}
}
ConvertTo-Json -Compress $answers
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([True]*3+[False]*5, json.loads(result.stdout))


if __name__ == '__main__':
    unittest.main()
