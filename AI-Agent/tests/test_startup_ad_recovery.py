import json
import unittest

from test_ad_close_stability import function_source, run_powershell


class StartupAdRecoveryTests(unittest.TestCase):
    def run_startup(self, first_state):
        command = f"""
$ErrorActionPreference = 'Stop'
$script:TopElevenPackage = 'eu.nordeus.topeleven.android'
$script:VisionAiProbeIntervalSeconds = 12
$script:VisionCacheByState = @{{}}
$script:probes = 0
$script:watchers = 0
$script:flow = ''
$script:activity = 'AdActivity'
function Get-BlueStacksForegroundState {{
    return [PSCustomObject]@{{Package=$script:TopElevenPackage; Activity=$script:activity}}
}}
function Test-TopElevenReturnedAfterAd {{ return ($script:watchers -gt 0) }}
function Get-TVFlowSnapshot {{ return [PSCustomObject]@{{state='unknown'}} }}
function Test-Cancelled {{}}
function Wait-Agent {{}}
function Add-Log {{}}
function Restore-AdFromGooglePlay {{ throw 'Back must not be sent on this screen' }}
function Test-TopElevenResourceHeaderReady {{ return $true }}
function Invoke-VisionAnalysis {{
    $script:probes++
    $kind = if ($script:probes -eq 1) {{ '{first_state}' }} else {{ 'top_eleven' }}
    if ($kind -eq 'unavailable') {{ return $null }}
    return [PSCustomObject]@{{
        accepted=($kind -ne 'unaccepted')
        decision=[PSCustomObject]@{{screenType=$kind; topElevenReturned=($kind -eq 'top_eleven'); recommendedAction='none'}}
    }}
}}
function Watch-TVAdvertisement {{
    param($Handle, $ManualReward, $ReturnFlow)
    $script:watchers++
    $script:flow = $ReturnFlow
    $script:activity = 'MainPlayerNativeActivity'
}}
{function_source('Restore-ExternalNavigationBeforeGameAction')}
$ready = Restore-ExternalNavigationBeforeGameAction ([IntPtr]1) 'Pocetak faze Uzmi 25 zelenih'
[PSCustomObject]@{{ready=$ready; probes=$script:probes; watchers=$script:watchers; flow=$script:flow}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout.strip())

    def test_store_with_stale_activity_does_not_start_ad_watcher(self):
        result = self.run_startup('top_eleven')
        self.assertTrue(result['ready'])
        self.assertEqual(1, result['probes'])
        self.assertEqual(0, result['watchers'])

    def test_visible_ad_uses_generic_recovery_not_mourinho(self):
        result = self.run_startup('ad')
        self.assertTrue(result['ready'])
        self.assertEqual(1, result['watchers'])
        self.assertEqual('recovery', result['flow'])

    def test_uncertain_analysis_retries_without_inventing_ad(self):
        for state in ('unknown', 'unavailable', 'unaccepted'):
            with self.subTest(state=state):
                result = self.run_startup(state)
                self.assertTrue(result['ready'])
                self.assertEqual(2, result['probes'])
                self.assertEqual(0, result['watchers'])


if __name__ == '__main__':
    unittest.main()
