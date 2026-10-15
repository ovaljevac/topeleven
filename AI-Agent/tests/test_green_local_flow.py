import json
import unittest
from pathlib import Path

from test_team_rest_free_button import x_detector as detector, green_store_screen, green_store_connected_background_screen
from test_external_navigation_recovery import function_source, run_powershell, function_body

ROOT = Path(__file__).resolve().parents[1]


class GreenLocalDetectorTests(unittest.TestCase):
    def real_store(self):
        return detector.load_image(ROOT/'tests/store-return-stale-activity.png')[78:681,150:1197].copy()

    def test_real_store_has_local_green_plus_and_immediately_ready_offer(self):
        image = self.real_store()
        header = detector.detect_top_resource_cards(image)
        self.assertTrue(header['found'])
        self.assertTrue(header['gameHeaderVerified'])
        self.assertAlmostEqual(.646, header['greenPlus']['x'], delta=.012)
        self.assertAlmostEqual(.089, header['greenPlus']['y'], delta=.008)
        offer = detector.detect_green_store_offer(image)
        self.assertEqual('ready', offer['offerState'])
        self.assertEqual([], offer['offerRows'])  # ready never waits for OCR

    def test_gray_besplatno_with_camera_and_green_icon_is_never_ready(self):
        import cv2
        import numpy as np
        image = self.real_store()
        roi = image[144:180,835:1008]
        hsv = cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
        blue = (hsv[:,:,0]>=85) & (hsv[:,:,0]<=125) & (hsv[:,:,1]>=65)
        roi[blue] = (85,85,85)
        offer = detector.detect_green_store_offer(image)
        self.assertEqual('unknown',offer['offerState'])
        self.assertTrue(any(row['greyBackground'] for row in offer['offerRows']))

    def test_loading_missing_and_morale_are_not_green_ready(self):
        import cv2
        for label in ('loading','plain'):
            offer = detector.detect_green_store_offer(green_store_screen(label))
            self.assertEqual('unknown',offer['offerState'])
        image = green_store_connected_background_screen('ready')
        cv2.circle(image,(1038,375),13,(220,80,40),-1)
        self.assertEqual('unknown',detector.detect_green_store_offer(image)['offerState'])

    def test_supplied_ads_and_blank_frames_do_not_have_game_header(self):
        for path in (ROOT/'debug').glob('20261008-*.json'):
            decision = json.loads(path.read_text(encoding='utf-8-sig')).get('decision',{})
            frame = path.with_suffix('.jpg')
            if decision.get('screenType') not in ('ad','unknown') or not frame.exists():
                continue
            with self.subTest(frame=frame.name):
                self.assertFalse(detector.detect_top_resource_cards(detector.load_image(frame)).get('gameHeaderVerified',False))

    def test_supplied_game_screens_have_verified_header_and_green_plus(self):
        for path in (ROOT/'debug').glob('20261008-*.json'):
            decision = json.loads(path.read_text(encoding='utf-8-sig')).get('decision',{})
            frame = path.with_suffix('.jpg')
            if decision.get('screenType') != 'top_eleven' or not frame.exists():
                continue
            with self.subTest(frame=frame.name):
                header = detector.detect_top_resource_cards(detector.load_image(frame))
                self.assertTrue(header.get('gameHeaderVerified',False))
                self.assertIsNotNone(header.get('greenPlus'))


class GreenLocalRuntimeTests(unittest.TestCase):
    def run_ps(self, names, code):
        result = run_powershell("$ErrorActionPreference='Stop'\n"+'\n'.join(function_source(name) for name in names)+'\n'+code)
        self.assertEqual(0,result.returncode,result.stderr+result.stdout)
        return result.stdout

    def test_ready_does_not_call_ai_or_ocr_and_uses_fresh_dynamic_point(self):
        result = self.run_ps(['Wait-GreenRewardOfferState'], r'''
function Invoke-VisionAnalysis { throw 'AI forbidden' }
function Read-LocalGreenOfferText { throw 'ready cannot require OCR' }
function Get-GreenRewardOfferSnapshot { $script:reads++; return @{offerState='ready'; x=.883; y=.265} }
function Wait-Agent { param($Milliseconds); if ($Milliseconds -gt 250) {throw 'offer unnecessarily delayed'} }
function Test-Cancelled {}
function Add-Log {}
$script:reads=0
$state=Wait-GreenRewardOfferState ([IntPtr]1)
@{state=$state; reads=$script:reads; x=$script:DetectedFreeButtonX; y=$script:DetectedFreeButtonY} | ConvertTo-Json -Compress
''')
        data = json.loads(result)
        self.assertEqual('ready',data['state'])
        self.assertEqual(2,data['reads'])
        self.assertEqual(.883,data['x'])

    def test_header_requires_two_fresh_local_frames_and_no_ai(self):
        result = self.run_ps(['Test-GreenGameReturned'], r'''
function Invoke-VisionAnalysis { throw 'AI forbidden' }
function Get-TopResourceCardsSnapshot { param($Handle,[switch]$ForceRefresh); if (-not $ForceRefresh) {throw 'stale frame'}; $script:reads++; return @{found=$true;gameHeaderVerified=$script:answers[$script:reads-1]} }
function Wait-Agent {}
$results=@()
foreach ($pair in @(@($true,$true), @($true,$false), @($false,$true))) {
 $script:answers=$pair; $script:reads=0
 $results += Test-GreenGameReturned ([IntPtr]1)
}
ConvertTo-Json -Compress $results
''')
        self.assertEqual([True,False,False],json.loads(result))

    def test_gray_or_limit_need_two_local_reads_and_unknown_breaks_stability(self):
        for state in ('grey','limit'):
            with self.subTest(state=state):
                self.run_ps(['Wait-GreenRewardOfferState'], r'''
function Invoke-VisionAnalysis { throw 'AI forbidden' }
function Test-Cancelled {}
function Wait-Agent {}
function Get-GreenRewardOfferSnapshot { $s=$script:states[$script:reads]; $script:reads++; return @{offerState=$s;x=$null;y=$null} }
$script:reads=0; $script:states=@('STATE','unknown','STATE','STATE')
$state=Wait-GreenRewardOfferState ([IntPtr]1)
if ($state -ne 'STATE' -or $script:reads -ne 4) {throw 'unstable offer accepted'}
'''.replace('STATE',state))

    def test_green_preflight_and_external_restore_do_not_call_ai_on_game(self):
        self.run_ps(['Restore-ExternalNavigationBeforeGameAction','Restore-AdFromGooglePlay'], r'''
$script:GreenLocalFlowActive=$true
function Wait-GreenGameReady {}
function Test-GreenGameReturned {return $true}
function Invoke-VisionAnalysis {throw 'AI forbidden'}
function Test-AiExternalNavigationVisible {throw 'external AI cannot precede local header'}
if (-not (Restore-ExternalNavigationBeforeGameAction ([IntPtr]1))) {throw 'local preflight lost'}
if (Restore-AdFromGooglePlay ([IntPtr]1) (Get-Date)) {throw 'game treated as store'}
''')

    def test_followup_accepts_header_before_external_ai_check(self):
        self.run_ps(['Wait-ForAdExitOrControl'], r'''
$script:GreenLocalFlowActive=$true
function Test-Cancelled {}
function Test-GreenGameReturned {return $true}
function Add-Log {}
function Restore-AdFromGooglePlay {throw 'external AI cannot precede local game'}
function Test-AiOnlyAdControlReady {throw 'AI forbidden'}
if ((Wait-ForAdExitOrControl ([IntPtr]1) 10 (Get-Date)) -ne 'exited') {throw 'return lost'}
''')

    def test_returned_game_prevents_clicking_previously_confirmed_ad_x(self):
        self.run_ps(['Confirm-AiAdCloseImmediatelyBeforeClick'], r'''
$script:GreenLocalFlowActive=$true
$script:DetectedAdCloseKind='close'
$script:DetectedAdCloseX=.96; $script:DetectedAdCloseY=.11
$script:DetectedAdCloseLocallyVerified=$true
function Test-GreenGameReturned {return $true}
function Wait-ForAdExitOrControl {throw 'game already returned'}
function Add-Log {}
if ((Confirm-AiAdCloseImmediatelyBeforeClick ([IntPtr]1)) -ne 'returned') {throw 'old ad X accepted on game'}
''')


if __name__=='__main__':
    unittest.main()
