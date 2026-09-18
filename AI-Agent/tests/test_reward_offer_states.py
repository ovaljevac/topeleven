import copy
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import VisionAgent as vision
from test_team_rest_free_button import function_body
from PIL import Image


def decision(state, target="green_store"):
    label = {"ready": "BESPLATNO", "grey": "BESPLATNO", "limit": "OGRAN. DOSTIGNUTO", "unknown": "UNKNOWN"}[state]
    return {"screenType": "top_eleven", "topElevenReturned": True,
            "recommendedAction": "none", "control": {"type": "none", "x": None, "y": None, "confidence": .99},
            "visibleText": f"TARGET:{target}; STATE:{state}; LABEL:{label}", "reason": "test"}


class OfferValidationTests(unittest.TestCase):
    def validate(self, raw, target="green_store"):
        return vision.validate_decision(raw, {"minimumConfidence": .85}, "reward_offer_" + target)[1]

    def test_all_states_and_both_targets(self):
        for target in ("green_store", "training_condition"):
            for state in ("ready", "grey", "limit", "unknown"):
                with self.subTest(target=target, state=state):
                    self.assertEqual([], self.validate(decision(state, target), target))

    def test_label_cannot_be_replaced_by_missing_button(self):
        raw = decision("limit")
        raw["visibleText"] = "TARGET:green_store; STATE:limit; LABEL:UNKNOWN"
        self.assertTrue(self.validate(raw))

    def test_wrong_resource_target_is_rejected(self):
        raw = decision("ready", "blue_morale")
        self.assertTrue(self.validate(raw))

    def test_ad_low_confidence_and_click_are_rejected(self):
        for mutation in ({"screenType": "ad"}, {"topElevenReturned": False},
                         {"control": {"type": "none", "x": None, "y": None, "confidence": .89}},
                         {"recommendedAction": "click_close", "control": {"type": "close", "x": .95, "y": .1, "confidence": .99}}):
            raw = decision("limit")
            raw.update(copy.deepcopy(mutation))
            self.assertTrue(self.validate(raw))

    def test_prompt_uses_original_image_and_exact_resource(self):
        picture = Image.new("RGB", (1024, 600))
        for target in ("green_store", "training_condition"):
            expected = "reward_offer_" + target
            prompt, supplied = vision.build_user_prompt(picture, expected)
            self.assertIs(supplied, picture)
            self.assertTrue(vision.expected_state_uses_original_image(expected))
            self.assertIn("OGRAN. DOSTIGNUTO", prompt)
            self.assertIn("Missing/covered", prompt)
        self.assertIn("Ignore blue MORAL", vision.build_user_prompt(picture, "reward_offer_green_store")[0])


@unittest.skipUnless(shutil.which("powershell.exe"), "Windows PowerShell required")
class OfferRuntimeTests(unittest.TestCase):
    source = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")

    def run_ps(self, functions, setup, check):
        definitions = "\n".join("function " + name + " {" + function_body(self.source, name) + "}" for name in functions)
        command = "$ErrorActionPreference='Stop'\n" + definitions + "\n" + setup + "\n" + check
        run = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=20)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)

    def test_grey_restarts_repeatedly_and_uses_new_handle(self):
        self.run_ps(["Wait-GreenRewardOffer"], """
function Wait-RewardOfferState { $script:calls++; if ($script:calls -le 3) { return 'grey' }; return 'ready' }
function Restart-TopElevenForStageRetry { $script:restarts++; return [IntPtr](10 + $script:restarts) }
function Open-Store { param($Handle); $script:opened=$Handle }
function Wait-Agent {}
function Set-Status {}
function Wait-ForCondition {}
$script:calls=0; $script:restarts=0
""", """
$result=Wait-GreenRewardOffer ([IntPtr]1)
if ($script:restarts -ne 3 -or $result.State -ne 'ready' -or $result.Handle -ne [IntPtr]13 -or $script:opened -ne [IntPtr]13) { throw 'resume failed' }
""")

    def test_limit_returns_without_restart_or_click(self):
        self.run_ps(["Wait-GreenRewardOffer"], """
function Wait-RewardOfferState { return 'limit' }
function Restart-TopElevenForStageRetry { throw 'must not restart' }
function Wait-ForCondition { throw 'must not look for a click' }
""", "$result=Wait-GreenRewardOffer ([IntPtr]1); if ($result.State -ne 'limit') { throw 'limit lost' }")

    def test_transient_grey_unknown_then_blue_does_not_restart(self):
        self.run_ps(["Wait-RewardOfferState"], """
$script:states=@('grey','unknown','ready'); $script:read=0; $script:VisionAiProbeIntervalSeconds=12
function Get-RewardOfferState { $value=$script:states[$script:read]; $script:read++; return $value }
function Test-Cancelled {}
function Add-Log {}
function Wait-Agent {}
""", "$result=Wait-RewardOfferState ([IntPtr]1) green_store; if ($result -ne 'ready' -or $script:read -ne 3) { throw 'unstable grey accepted' }")

    def test_unknown_timeout_is_error_not_completion(self):
        self.run_ps(["Wait-RewardOfferState"], "", """
$caught=$false
try { Wait-RewardOfferState ([IntPtr]1) green_store 0 } catch { $caught=$true }
if (-not $caught) { throw 'missing offer treated as success' }
""")

    def test_limit_and_grey_need_two_fresh_reads(self):
        self.run_ps(["Wait-RewardOfferState"], """
$script:VisionAiProbeIntervalSeconds=12
function Get-RewardOfferState { $script:reads++; return $script:testState }
function Test-Cancelled {}
function Add-Log {}
function Wait-Agent { param($Milliseconds); if ($Milliseconds -lt 12000) { throw 'probe too fast' } }
""", """
foreach ($state in @('limit','grey')) {
    $script:testState=$state; $script:reads=0
    $result=Wait-RewardOfferState ([IntPtr]1) green_store
    if ($result -ne $state -or $script:reads -ne 2) { throw 'missing fresh confirmation' }
}
""")

    def test_stop_propagates_out_of_offer_wait(self):
        self.run_ps(["Wait-RewardOfferState"], "function Test-Cancelled { throw [System.OperationCanceledException]::new('stop') }", """
$caught=$false
try { Wait-RewardOfferState ([IntPtr]1) green_store } catch [System.OperationCanceledException] { $caught=$true }
if (-not $caught) { throw 'stop ignored' }
""")

    def test_training_limit_and_grey_exit_before_local_click_wait(self):
        self.run_ps(["Wait-TrainingFreeButton"], """
function Wait-RewardOfferState { return $script:testState }
function Get-TrainingPlayerFlowSnapshot { throw 'must not click/check old profile' }
""", """
foreach ($state in @('limit','grey')) {
    $script:testState=$state
    $result=Wait-TrainingFreeButton ([IntPtr]1)
    if ($result.OfferState -ne $state -or $result.ready) { throw 'training state lost' }
}
""")

    def test_training_restart_reopens_setup_then_limit_ends_without_training(self):
        self.run_ps(["Run-TrainingPlayerAutomation"], """
Add-Type -AssemblyName System.Drawing
Add-Type 'public class Win32Agent { public static bool SetForegroundWindow(System.IntPtr h) {return true;} }'
$form=[PSCustomObject]@{TopMost=$true}; $script:recoveries=0; $script:restarts=0; $script:trainingStarts=0; $script:exhaustionPending=$false
function Get-TrainingPlayerFlowSnapshot {
    if ($script:exhaustionPending) {
        $script:exhaustionPending=$false
        return [PSCustomObject]@{state='exhausted_players'; closeButton=[PSCustomObject]@{x=.8;y=.3}}
    }
    return [PSCustomObject]@{state='training_home'; reportsButton=[PSCustomObject]@{x=.5;y=.9}}
}
function Wait-TrainingPlayerState { return [PSCustomObject]@{repeatButton=[PSCustomObject]@{x=.9;y=.3}; startButton=[PSCustomObject]@{x=.7;y=.9}} }
function Restore-TrainingPlayerCondition { $script:recoveries++; if ($script:recoveries -eq 1) {return 'restart_required'}; return 'limit_reached' }
function Restart-TopElevenForStageRetry { $script:restarts++; return [IntPtr]2 }
function Click-TrainingPlayerRelative { param($Handle); $script:lastClickHandle=$Handle }
function Click-TrainingPlayerClose {}
function Click-Relative {
    if ($script:restarts -gt 0) { throw 'must recover condition before starting training after restart' }
    $script:trainingStarts++; $script:exhaustionPending=$true
}
function Wait-Agent {}
function Test-Cancelled {}
function Add-Log {}
function Set-Status {}
""", """
Run-TrainingPlayerAutomation ([IntPtr]1)
if ($script:restarts -ne 1 -or $script:recoveries -ne 2 -or $script:trainingStarts -ne 1 -or $script:lastClickHandle -ne [IntPtr]2 -or -not $form.TopMost) { throw 'training did not resume safely' }
""")


if __name__ == "__main__":
    unittest.main()
