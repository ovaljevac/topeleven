import json
import unittest
from pathlib import Path

from test_ad_close_stability import function_source, run_powershell
from test_training_player_flow import x_detector


class StoreReturnTests(unittest.TestCase):
    def test_reported_screenshot_is_store(self):
        image = x_detector.load_image(str(Path(__file__).with_name('store-return-stale-activity.png')))
        window = image[77:682, 149:1199]
        for width, height in ((1050, 605), (1280, 738)):
            result = x_detector.detect_team_rest_free_button(x_detector.cv2.resize(window, (width, height)))
            self.assertTrue(result['storeLoaded'])
            self.assertTrue(result['ready'])

    def probe(self, source='player_log', package='eu.nordeus.topeleven.android', second=True, accepted=True):
        code = f"""
$ErrorActionPreference='Stop'
$script:frames=0; $script:waits=0
function Add-Log {{}}
function Wait-Agent {{ param($ms); if ($ms -lt 300) {{throw 'same frame'}}; $script:waits++ }}
function Invoke-VisionAnalysis {{
    return [PSCustomObject]@{{accepted=${str(accepted).lower()}; decision=[PSCustomObject]@{{
        screenType='top_eleven'; topElevenReturned=$true; recommendedAction='none'
    }}}}
}}
function Test-TopElevenReturnedAfterAd {{ return $false }}
function Get-BlueStacksForegroundState {{
    return [PSCustomObject]@{{Source='{source}'; Package='{package}'; Activity='AdActivity'}}
}}
function Get-TeamRestFreeButtonSnapshot {{
    $script:frames++
    return [PSCustomObject]@{{storeLoaded=($script:frames -eq 1 -or ${str(second).lower()})}}
}}
{function_source('Test-StoreReturnVisualProof')}
{function_source('Test-AiOnlyAdControlReady')}
$ready=Test-AiOnlyAdControlReady ([IntPtr]1) 'ad_control_ai_only_test'
[PSCustomObject]@{{returned=$script:AiTopElevenReturned; ready=$ready; frames=$script:frames; waits=$script:waits; x=$script:DetectedAdCloseX}} | ConvertTo-Json -Compress
"""
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout.strip())

    def test_ai_store_return_overrides_stale_activity_without_adb(self):
        result = self.probe()
        self.assertTrue(result['returned'])
        self.assertFalse(result['ready'])
        self.assertIsNone(result['x'])
        self.assertEqual(0, result['frames'])
        self.assertEqual(0, result['waits'])

    def test_stale_chrome_log_cannot_veto_visible_store(self):
        self.assertTrue(self.probe(package='com.android.chrome')['returned'])

    def test_activity_cannot_override_accepted_visual_return(self):
        for package in ('com.android.chrome', 'com.android.vending'):
            self.assertTrue(self.probe(source='adb', package=package)['returned'])

    def test_disappearing_store_and_unaccepted_ai_do_not_finish_ad(self):
        self.assertTrue(self.probe(second=False)['returned'])
        result = self.probe(accepted=False)
        self.assertFalse(result['returned'])
        self.assertEqual(0, result['frames'])

    def test_old_external_log_does_not_send_back_when_ai_sees_game(self):
        code = """
$ErrorActionPreference='Stop'
function Get-BlueStacksForegroundState { return [PSCustomObject]@{Package='com.android.chrome'; Source='player_log'; EventTime=(Get-Date)} }
function Test-AiExternalNavigationVisible { return $false }
function Send-BlueStacksBack { throw 'Back on game' }
""" + function_source('Restore-AdFromGooglePlay') + """
if (Restore-AdFromGooglePlay ([IntPtr]1) (Get-Date)) { throw 'stale log accepted as external app' }
"""
        result = run_powershell(code)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
