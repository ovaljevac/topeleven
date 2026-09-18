import unittest
import shutil
import subprocess
from pathlib import Path
from test_external_navigation_recovery import function_source
from test_training_player_flow import x_detector as detector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class TrainingRejectionTests(unittest.TestCase):
    def test_black_white_and_random_frames_are_unknown(self):
        frames = [np.zeros((600, 1024, 3), np.uint8), np.full((600, 1024, 3), 255, np.uint8),
                  np.random.default_rng(27).integers(0, 256, (600, 1024, 3), dtype=np.uint8)]
        for frame in frames:
            result = detector.detect_training_player_flow(frame)
            self.assertEqual('unknown', result['state'])
            self.assertNotIn('closeButton', result)

    def test_erased_result_x_is_not_a_click(self):
        frame = detector.load_image(str(ROOT / 'Trening igraca' / '5.png'))
        h, w = frame.shape[:2]
        frame[int(h*.05):int(h*.16), int(w*.90):] = 0
        result = detector.detect_training_player_flow(frame)
        self.assertEqual('unknown', result['state'])
        self.assertNotIn('closeButton', result)

    def test_reference_buttons_remain_grounded_when_scaled(self):
        for index in (2, 3, 4, 5):
            original = detector.load_image(str(ROOT / 'Trening igraca' / f'{index}.png'))
            scaled = detector.cv2.resize(original, (1280, 720))
            result = detector.detect_training_player_flow(scaled)
            self.assertNotEqual('unknown', result['state'])


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows required')
class SafetyRuntimeTests(unittest.TestCase):
    def test_training_wait_polls_locally_without_ai(self):
        self.run_code(['Wait-TrainingPlayerState'], """
$script:reads=0
$script:expired=$false
function Get-Date {
    $now=[datetime]'2026-09-03T14:02:10'
    if ($script:expired) { return $now.AddSeconds(60) }
    return $now
}
function Test-Cancelled {}
function Wait-Agent { if ($script:remainUnknown) { $script:expired=$true } }
function Get-TrainingPlayerFlowSnapshot {
    $script:reads++
    if ($script:reads -eq 1 -or $script:remainUnknown) { return [PSCustomObject]@{state='unknown'} }
    return [PSCustomObject]@{state='setup';startButton=@{x=.86;y=.36}}
}
function Try-RecoverConnectionInterruptedPopup { throw 'unexpected AI popup probe' }
function Invoke-VisionAnalysis { throw 'unexpected AI analysis' }
""", """
$result=Wait-TrainingPlayerState ([IntPtr]::Zero) @('setup') 25
if ($result.state -ne 'setup' -or $script:reads -ne 2) { throw 'local polling did not recognize setup' }
$script:reads=0; $script:expired=$false; $script:remainUnknown=$true
$failed=$false
try { Wait-TrainingPlayerState ([IntPtr]::Zero) @('setup') 25 }
catch { $failed=$true }
if (-not $failed) { throw 'unknown screen accepted' }
""")

    def run_code(self, names, setup, assertions):
        command = "$ErrorActionPreference='Stop'\nAdd-Type -AssemblyName System.Drawing\n" + '\n'.join(function_source(n) for n in names) + '\n' + setup + '\n' + assertions
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_training_opens_fixed_player_row_only_after_reported_exhaustion(self):
        self.run_code(['Run-TrainingPlayerAutomation'], """
Add-Type 'public static class Win32Agent { public static bool SetForegroundWindow(System.IntPtr h) { return true; } }'
$form = [PSCustomObject]@{TopMost=$true}
function Test-Cancelled {}
function Set-Status {}
function Add-Log {}
function Wait-Agent {}
function Click-Relative { $script:starts++ }
function Click-TrainingPlayerRelative {}
function Click-TrainingPlayerClose { $script:closes++ }
function Set-AgentCheckpointStep { throw 'cycle_complete' }
function Get-TrainingPlayerFlowSnapshot {
    $script:snapshots++
    if ($script:snapshots -le 2) {
        return [PSCustomObject]@{state='training_home';reportsButton=@{x=.5;y=.9}}
    }
    return [PSCustomObject]@{state=$script:outcome;closeButton=@{x=.83;y=.3}}
}
function Wait-TrainingPlayerState {
    param($Handle,$ExpectedStates,$TimeoutSeconds)
    return [PSCustomObject]@{state=$ExpectedStates[0];repeatButton=@{x=.9;y=.3};startButton=@{x=.8;y=.3}}
}
function Get-AiTrainingSetupCondition {
    if ($script:closes -ne 1) { throw 'AI ran before exhaustion close' }
    $script:aiReads++
    return [PSCustomObject]@{HasLow=$true;Condition=29;X=.5;Y=.5}
}
function Restore-TrainingPlayerCondition { $script:recoveries++; return 'limit_reached' }
""", """
foreach ($outcome in @('training_result','exhausted_players')) {
    $script:outcome=$outcome
    $script:starts=0; $script:closes=0; $script:snapshots=0; $script:aiReads=0; $script:recoveries=0
    $script:Checkpoint=[PSCustomObject]@{TrainingCycles=0}
    try { Run-TrainingPlayerAutomation ([IntPtr]::Zero) }
    catch { if ($_.Exception.Message -ne 'cycle_complete') { throw } }
    if ($script:starts -ne 1) { throw 'unexpected training attempts' }
    if ($outcome -eq 'training_result') {
        if ($script:aiReads -ne 0 -or $script:recoveries -ne 0 -or $script:Checkpoint.TrainingCycles -ne 1) { throw 'normal training did not skip AI' }
    } else {
        if ($script:aiReads -ne 0 -or $script:recoveries -ne 1 -or $script:Checkpoint.TrainingCycles -ne 0) { throw 'exhaustion did not recover without counting a cycle' }
    }
    if (-not $form.TopMost) { throw 'form state was not restored' }
}
""")

    def test_typed_recovery_does_not_depend_on_message(self):
        self.run_code(['New-AgentFailure', 'Test-StageFailureRequiresHardRecovery'], '', """
$sampleFailure=New-AgentFailure AdTimeout 'arbitrary translated text'
if (-not (Test-StageFailureRequiresHardRecovery $sampleFailure)) { throw 'typed timeout lost' }
$wrapped=[System.Exception]::new('wrapper', $sampleFailure)
if (-not (Test-StageFailureRequiresHardRecovery $wrapped)) { throw 'inner category lost' }
if (Test-StageFailureRequiresHardRecovery ([System.Exception]::new('reklama nije zavrsena u roku od 5 minuta'))) { throw 'message still triggers restart' }
foreach ($kind in @('ScreenUnknown','ExternalNavigationStuck','CampusBoundaryUnknown','FocusLost')) {
    if (Test-StageFailureRequiresHardRecovery (New-AgentFailure $kind 'reklama nije zatvorena')) { throw 'ordinary error restarts game' }
}
""")

    def test_ready_changing_to_grey_or_limit_is_reclassified(self):
        self.run_code(['Wait-RewardOfferState'], """
function Test-Cancelled {}
function Add-Log {}
function Wait-Agent {}
$script:VisionAiProbeIntervalSeconds=12
function Get-RewardOfferState { $script:reads++; if ($script:reads -eq 1) { return 'ready' }; return $script:targetState }
""", """
foreach ($target in @('grey','limit')) {
    $script:reads=0; $script:targetState=$target
    $answer=Wait-RewardOfferState ([IntPtr]1) green_store -ReadyCheck { return $false }
    if ($answer -ne $target -or $script:reads -ne 3) { throw 'changed offer lost' }
}
""")

    def test_training_local_failure_does_not_hide_limit(self):
        self.run_code(['Wait-RewardOfferState', 'Wait-TrainingFreeButton'], """
function Test-Cancelled {}
function Add-Log {}
function Wait-Agent {}
$script:VisionAiProbeIntervalSeconds=12; $script:reads=0
function Get-RewardOfferState { $script:reads++; if ($script:reads -eq 1) {return 'ready'}; return 'limit' }
function Get-TrainingPlayerFlowSnapshot { return [PSCustomObject]@{state='unknown'} }
""", """
$result=Wait-TrainingFreeButton ([IntPtr]1)
if ($result.OfferState -ne 'limit' -or $result.ready) { throw 'training ignored new limit' }
""")

    def test_boundary_rejects_stuck_drag_and_accepts_reversible_same_cards(self):
        self.run_code(['Confirm-CampusStripBoundary'], """
$script:moved=$false
function Move-CampusObjectStripChecked { return $script:moved }
function Get-CampusFlowSnapshot { return [PSCustomObject]@{objectStrip=[PSCustomObject]@{verified=$true;cards=@([PSCustomObject]@{x=.1;identity=@(1)*128},[PSCustomObject]@{x=.2;identity=@(2)*128})}} }
""", """
if (Confirm-CampusStripBoundary ([IntPtr]1) $true) { throw 'failed drag accepted as edge' }
$script:moved=$true
if (-not (Confirm-CampusStripBoundary ([IntPtr]1) $true)) { throw 'reversible edge rejected' }
""")

    def test_external_return_for_each_local_flow(self):
        setup = """
$script:clock=[datetime]'2026-09-02T21:22:55'; $script:restores=0; $script:VisionAiProbeIntervalSeconds=12
function Get-Date { $script:clock=$script:clock.AddSeconds(2); return $script:clock }
function Test-Cancelled {}
function Set-Status {}
function Add-Log {}
function Start-Sleep {}
function Wait-Agent {}
function Restore-AdFromGooglePlay { $script:restores++; return ($script:restores -eq 1) }
function Get-TVFlowSnapshot { return [PSCustomObject]@{state=$script:tvState} }
function Get-TrainingPlayerFlowSnapshot { return [PSCustomObject]@{state='player_detail';profileVerified=$true} }
function Get-PutSavezaFlowSnapshot { return [PSCustomObject]@{state='path';closeButton=[PSCustomObject]@{x=.9;y=.1}} }
function Test-TopElevenReturnedAfterAd { throw 'stale activity must not veto verified return' }
"""
        self.run_code(['Watch-TVAdvertisement'], setup, """
foreach ($flow in @('training_player','put_saveza','tv')) {
    $script:restores=0; $script:tvState='tv'
    $expected=if ($flow -eq 'tv') {'tv'} else {'top_eleven'}
    if ((Watch-TVAdvertisement ([IntPtr]1) $false $flow) -ne $expected) { throw 'return failed' }
}
$script:restores=0; $script:tvState='manual_3'
if ((Watch-TVAdvertisement ([IntPtr]1) $true tv) -ne 'manual_3') { throw 'manual return failed' }
""")

    def test_game_without_departure_does_not_count_as_ad_return(self):
        self.run_code(['Watch-TVAdvertisement'], """
$script:clock=[datetime]'2026-09-02T21:22:55'; $script:VisionAiProbeIntervalSeconds=12
function Get-Date { $script:clock=$script:clock.AddSeconds(2); return $script:clock }
function Test-Cancelled {}
function Set-Status {}
function Restore-AdFromGooglePlay { return $false }
function Get-TrainingPlayerFlowSnapshot { throw 'incorrect early local return path' }
function Test-TopElevenReturnedAfterAd { throw 'expected_guard' }
""", """
$guarded=$false
try { Watch-TVAdvertisement ([IntPtr]1) $false training_player } catch {
    if ($_.Exception.Message -ne 'expected_guard') {throw}; $guarded=$true
}
if (-not $guarded) { throw 'game was mistaken for completed ad' }
""")

    def test_back_budget_and_no_progress_are_terminal(self):
        setup = """
$script:clock=[datetime]'2026-09-02T21:22:55'; $script:ExternalNavigationBackAttempts=6
function Get-Date { $script:clock=$script:clock.AddSeconds(3); return $script:clock }
function Test-AiExternalNavigationVisible { return $true }
function Add-Log {}
function Set-Status {}
function Wait-Agent {}
function Send-BlueStacksBack { $script:sent++ }
function Get-AdNavigationFingerprint { $script:frames++; $value=if ($script:changing) {($script:frames % 2)*100} else {0}; return ,(@($value)*576) }
"""
        self.run_code(['New-AgentFailure', 'Restore-AdFromGooglePlay'], setup, """
foreach ($changing in @($false,$true)) {
    $script:changing=$changing; $script:sent=0; $script:frames=0
    $adTime=Get-Date
    $caught=$false
    try {
        for ($i=0;$i -lt 9;$i++) {
            $script:LastGooglePlayClickAt=Get-Date
            Restore-AdFromGooglePlay ([IntPtr]1) $adTime | Out-Null
        }
    } catch { if ($_.Exception.Data['AgentFailureKind'] -ne 'ExternalNavigationStuck') {throw}; $caught=$true }
    $expected=if ($changing) {6} else {3}
    if (-not $caught -or $script:sent -ne $expected) { throw "invalid Back count $($script:sent)" }
}
""")


if __name__ == '__main__':
    unittest.main()
