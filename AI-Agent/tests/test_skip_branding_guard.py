import json
import tempfile
import unittest
from pathlib import Path

from test_vision_agent import vision_agent as vision, decision
from test_training_player_flow import x_detector as detector
from test_external_navigation_recovery import function_source, run_powershell

ROOT = Path(__file__).resolve().parents[1]


class SkipBrandingGuardTests(unittest.TestCase):
    def brand(self):
        return detector.load_image(ROOT / 'tests/kingshot-false-skip-20261008.png')

    def test_reported_logo_never_becomes_skip_on_repeated_frames(self):
        image = self.brand()
        for scale in (1, 1.5, 2):
            frame = detector.cv2.resize(image, None, fx=scale, fy=scale)
            self.assertIsNone(detector._detect_double_chevron_control(frame))
            for _ in range(3):
                # Even a previous perfectly matching patch is no type proof.
                result = detector.refine_skip_control_near_point(
                    frame, {'x': .118, 'y': .105}, {'image': 'same-static-logo'})
                self.assertFalse(result['found'])

    def test_bad_ai_label_cannot_authorize_logo_click(self):
        rgb = detector.cv2.cvtColor(self.brand(), detector.cv2.COLOR_BGR2RGB)
        image = vision.Image.fromarray(rgb)
        raw = decision(action='click_skip', control='skip', x=.118, y=.105, confidence=.99)
        refined, proof = vision.refine_ai_skip_on_fresh_frame(image, image, raw)
        self.assertFalse(proof['applied'])
        self.assertEqual(raw, refined)
        self.assertIsNotNone(proof['textCheck'])
        # The strict fallback for AI none must not rediscover this false Skip.
        self.assertFalse(detector.run_detector(self.brand(), live=True)['found'])

    def test_letter_h_is_not_a_filled_fast_forward_symbol(self):
        component = detector.np.zeros((12, 16), dtype=bool)
        component[:, :3] = True
        component[:, -3:] = True
        component[5:7] = True
        self.assertFalse(detector._looks_like_filled_fast_forward_component(component))

    def test_real_open_chevrons_still_pass_current_frame_check(self):
        image = detector.np.zeros((615, 1067, 3), detector.np.uint8)
        detector.cv2.circle(image, (33, 76), 18, (145, 155, 165), -1)
        detector.cv2.putText(image, '>>', (24, 81), detector.cv2.FONT_HERSHEY_SIMPLEX,
                            .45, (255, 255, 255), 1, detector.cv2.LINE_AA)
        result = detector.refine_skip_control_near_point(image, {'x': 33/1067, 'y': 76/615})
        self.assertTrue(result['found'])
        self.assertEqual('ai-local-fresh-skip-chevron', result['method'])

    def test_only_literal_skip_label_can_authorize_ocr(self):
        code = function_source('Get-AdSkipTextProof') + r'''
$ErrorActionPreference='Stop'
function Add-Log {}
function Read-LocalGreenOfferText {return @{Text=$script:label;Words=@([PSCustomObject]@{X=4;Y=4;Width=80;Height=32})}}
$crop=@{image='selected-crop';scale=4;sourceBox=@(900,60,960,90);windowSize=@(1000,600);x=.911;y=.1083}
$answers=@()
foreach($label in @('Skip','Skip Ad','Skip Video','Kingshot','Google Play','Download Now','Skip 5','Skip Install','Interested','Not interested','')) {
 $script:label=$label
 $answers+=($null -ne (Get-AdSkipTextProof $crop))
}
ConvertTo-Json -Compress $answers
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([True, True, True] + [False]*8, json.loads(result.stdout))

    def test_skip_ocr_cannot_override_other_validation_failure(self):
        code = function_source('Confirm-AdSkipTextCandidate') + r'''
$ErrorActionPreference='Stop'
function Get-AdSkipTextProof {throw 'must not override other rejection'}
$result=@{accepted=$false;decision=@{recommendedAction='click_skip'};errors=@('Skip was not verified on fresh frame','invalid coordinate')}
$result=Confirm-AdSkipTextCandidate $result
if($result.accepted){throw 'invalid Skip accepted'}
'checked'
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_native_windows_ocr_proves_skip_and_rejects_logo_and_blank(self):
        frame = detector.np.full((600, 1000, 3), 35, detector.np.uint8)
        detector.cv2.putText(frame, 'Skip', (908, 75), detector.cv2.FONT_HERSHEY_SIMPLEX,
                            .55, (255, 255, 255), 1, detector.cv2.LINE_AA)
        control = {'x': .93, 'y': .115}
        crops = [
            detector.skip_control_text_crop(frame, control),
            detector.skip_control_text_crop(self.brand(), {'x': .118, 'y': .105}),
            detector.skip_control_text_crop(detector.np.full_like(frame, 35), control),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'skip-crops.json'
            path.write_text(json.dumps(crops))
            code = '\n'.join(function_source(name) for name in (
                'Wait-LocalOcrOperation', 'Read-LocalGreenOfferText', 'Get-AdSkipTextProof'))
            code += "\n$ErrorActionPreference='Stop'\nfunction Test-Cancelled {}\nfunction Add-Log {}\n"
            code += "$crops=Get-Content -LiteralPath '" + str(path).replace("'", "''") + "' -Raw | ConvertFrom-Json\n"
            code += "@($crops | ForEach-Object {Get-AdSkipTextProof $_}) | ConvertTo-Json -Compress\n"
            result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        proofs = json.loads(result.stdout)
        if isinstance(proofs, dict):
            proofs = [proofs]
        self.assertEqual(1, len(proofs), proofs)
        self.assertEqual('skip', proofs[0]['kind'])
        self.assertAlmostEqual(.93, proofs[0]['x'], delta=.008)
        self.assertAlmostEqual(.115, proofs[0]['y'], delta=.008)

    def test_preclick_cancelled_when_ocr_reads_brand_instead_of_skip(self):
        code = '\n'.join(function_source(name) for name in (
            'Get-AdSkipTextProof', 'Confirm-AdSkipImmediatelyBeforeClick', 'Click-Relative')) + r'''
$ErrorActionPreference='Stop'
$script:DryRun=$true
function Test-Cancelled {}
function Set-BlueStacksWindowForeground {return $true}
function Start-XDetector {}
function Get-WindowRectangle {return @{Left=0;Top=0;Right=361;Bottom=616}}
function Read-LocalGreenOfferText {return @{Text='Kingshot';Words=@()}}
function Read-AgentProcessLine {return '{"found":false,"skipTextCheck":{"image":"brand"}}'}
function Add-Log {param($Text);if($Text -like '*DRY RUN*'){throw 'logo click executed'}}
function Set-AgentPendingAction {throw 'unconfirmed click prepared'}
$script:XDetectorProcess=@{StandardInput=(New-Object System.IO.StringWriter)}
Click-Relative ([IntPtr]1) .118 .105 'Skip - test'
if($null -ne $script:DetectedAdCloseX){throw 'bad coordinate survived'}
'checked'
'''
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
