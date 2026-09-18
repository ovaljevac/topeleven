import shutil
import subprocess
import unittest
from pathlib import Path
from test_team_rest_free_button import function_body

SOURCE = (Path(__file__).resolve().parents[1] / 'TopElevenAgent.ps1').read_text(encoding='utf-8-sig')


class CampusExternalReturnTests(unittest.TestCase):
    def test_pause_precedes_post_ad_snapshot(self):
        body = function_body(SOURCE, 'Invoke-CampusStripMaintenance')
        start = body.index("Watch-TVAdvertisement $Handle $false 'campus'")
        pause = body.index('Wait-Agent 5000', start)
        snapshot = body.index("Wait-CampusFlowState $Handle @('campus_detail')", start)
        self.assertLess(start, pause)
        self.assertLess(pause, snapshot)

    @unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell required')
    def test_external_departure_allows_two_campus_frames_without_ai_ad_sample(self):
        body = function_body(SOURCE, 'Watch-TVAdvertisement')
        command = """
$ErrorActionPreference='Stop'
$script:clock=[datetime]'2026-09-02T21:22:55'
$script:restores=0; $script:frames=0
$script:VisionAiProbeIntervalSeconds=12
function Get-Date { $script:clock=$script:clock.AddSeconds(2); return $script:clock }
function Test-Cancelled {}
function Set-Status {}
function Add-Log {}
function Start-Sleep {}
function Wait-Agent {}
function Restore-AdFromGooglePlay { $script:restores++; return ($script:restores -eq 1) }
function Get-CampusFlowSnapshot { $script:frames++; return [PSCustomObject]@{state='campus_detail';objectStrip=[PSCustomObject]@{verified=$true}} }
function Test-TopElevenReturnedAfterAd { throw 'must not require MainPlayerNativeActivity for verified Campus return' }
""" + '\nfunction Watch-TVAdvertisement {' + body + """
}
$result=Watch-TVAdvertisement ([IntPtr]1) $false 'campus'
if ($result -ne 'top_eleven' -or $script:frames -ne 2) { throw 'Campus return was not confirmed twice' }
"""
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_external_path_does_not_remove_departure_or_strip_guards(self):
        body = function_body(SOURCE, 'Watch-TVAdvertisement')
        self.assertIn('$externalDepartureObserved = $false', body)
        self.assertIn("$ReturnFlow -eq 'campus' -and $adObserved", body)
        self.assertIn('($aiAdVisuallyObserved -or $externalDepartureObserved)', body)
        self.assertIn("$campusReturn.state -eq 'campus_detail' -and $campusReturn.objectStrip.verified", body)
        restore = body.index('if (Restore-AdFromGooglePlay')
        clear = body.index('$campusReturnStableCount = 0', restore)
        self.assertLess(clear, body.index("$ReturnFlow -eq 'campus'", restore))


if __name__ == '__main__':
    unittest.main()
