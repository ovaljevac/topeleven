import ast
import asyncio
import json
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path

from test_ad_close_stability import function_source, run_powershell
from test_vision_agent import decision, vision_agent

ROOT = Path(__file__).resolve().parents[1]


def bot_method(name, env):
    tree = ast.parse((ROOT / 'discord_bot.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TopElevenBot')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<bot-test>', 'exec'), env)
    return env[name]


class AuditRegressions(unittest.TestCase):
    def test_cancel_during_ai_request_is_not_reported_as_provider_failure(self):
        code = """
$ErrorActionPreference='Stop'
$script:VisionEnabled=$true
$script:VisionUnavailableUntil=[datetime]::MinValue
$script:VisionCacheByState=@{}
$script:VisionAgentProcess=[PSCustomObject]@{HasExited=$false}
function Start-VisionAgent { return $true }
function Get-WindowRectangle { throw [System.OperationCanceledException]::new('cancel') }
function Add-Log { throw 'cancellation was logged as provider error' }
""" + function_source('Invoke-VisionAnalysis') + """
$cancelled=$false
try { Invoke-VisionAnalysis ([IntPtr]1) 'test' } catch [System.OperationCanceledException] { $cancelled=$true }
if (-not $cancelled) { throw 'cancellation swallowed' }
"""
        run = run_powershell(code)
        self.assertEqual(0, run.returncode, run.stderr)

    def test_training_popup_recovery_runs_after_local_grace_period(self):
        code = """
$ErrorActionPreference='Stop'
$script:clock=[datetime]'2026-09-05T10:00:00'; $script:recovered=$false
function Get-Date { return $script:clock }
function Test-Cancelled {}
function Wait-Agent { $script:clock=$script:clock.AddSeconds(3) }
function Get-TrainingPlayerFlowSnapshot {
    $state=if ($script:recovered) {'setup'} else {'unknown'}
    return [PSCustomObject]@{state=$state}
}
function Try-RecoverConnectionInterruptedPopup { $script:recovered=$true; return $true }
""" + function_source('Wait-TrainingPlayerState') + """
if ((Wait-TrainingPlayerState ([IntPtr]1) @('setup') 25).state -ne 'setup') { throw 'popup blocked training' }
if (-not $script:recovered) { throw 'popup not checked' }
"""
        run = run_powershell(code)
        self.assertEqual(0, run.returncode, run.stderr)

    def test_malformed_ai_fields_are_rejected_without_exception(self):
        for field in ('screenType', 'recommendedAction', 'control'):
            for value in (None, [], {}, 42):
                with self.subTest(field=field, value=value):
                    raw = decision()
                    raw[field] = value
                    _, errors = vision_agent.validate_decision(raw, {'minimumConfidence': .85}, 'ad_control_ai_only_test')
                    self.assertTrue(errors)
        raw = decision()
        raw['control']['type'] = []
        self.assertTrue(vision_agent.validate_decision(raw, {'minimumConfidence': .85})[1])
        raw = decision()
        raw.update(screenType='top_eleven', topElevenReturned='false')
        self.assertTrue(vision_agent.validate_decision(raw, {'minimumConfidence': .85}, 'ad_control_ai_only_test')[1])

    def test_invalid_click_coordinates_fail_before_any_side_effect(self):
        code = """
$ErrorActionPreference='Stop'
function Test-Cancelled {}
function Set-AgentPendingAction { throw 'side_effect' }
""" + function_source('Click-Relative') + function_source('Click-GameRelative') + """
foreach ($name in @('Click-Relative', 'Click-GameRelative')) {
    foreach ($x in @(-0.01, 1.01, [double]::NaN, [double]::PositiveInfinity)) {
        $rejected=$false
        try { & $name ([IntPtr]1) $x 0.5 'test' } catch {
            if ($_.Exception.Message -notlike 'Neispravne koordinate*') { throw }
            $rejected=$true
        }
        if (-not $rejected) { throw 'invalid click accepted' }
    }
}
"""
        run = run_powershell(code)
        self.assertEqual(0, run.returncode, run.stderr)

    def test_wake_return_is_used_without_second_ai_request(self):
        code = """
$ErrorActionPreference='Stop'
$script:TopElevenPackage='eu.nordeus.topeleven.android'
$script:VisionEnabled=$true; $script:VisionAiProbeIntervalSeconds=12
$script:AdWakeTapAfterSeconds=0; $script:AdWakeTapMaximum=2
$script:clock=[datetime]'2026-09-05T10:00:00'
function Get-Date { $script:clock=$script:clock.AddSeconds(2); return $script:clock }
function Test-Cancelled {}
function Add-Log {}
function Set-Status {}
function Wait-Agent {}
function Restore-AdFromGooglePlay { return $false }
function Test-TopElevenReturnedAfterAd { return $false }
function Get-BlueStacksForegroundState {
    return [PSCustomObject]@{Package=$script:TopElevenPackage; Activity='AdActivity'; EventTime=(Get-Date)}
}
function Test-AdWakeTapAllowed {
    $script:AiTopElevenReturned=$true
    $script:AiAdVisible=$false
    $script:DetectedAdCloseX=$null; $script:DetectedAdCloseY=$null
    return $false
}
function Test-AiOnlyAdControlReady { throw 'wake result discarded' }
function Click-Relative { throw 'must not click returned game' }
""" + function_source('Watch-TVAdvertisement') + """
if ((Watch-TVAdvertisement ([IntPtr]1) $false 'recovery') -ne 'top_eleven') { throw 'return ignored' }
"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'wake.ps1'
            path.write_text(code, encoding='utf-8-sig')
            run = subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(0, run.returncode, run.stderr)

    def test_discord_network_error_does_not_release_live_process(self):
        async def scenario():
            process = types.SimpleNamespace(returncode=None)
            run = types.SimpleNamespace(process=process, key='test', stop_path=Path('nonexistent-test-stop'))
            owner = types.SimpleNamespace(running=run, reads=0, sleeps=0)
            async def sleep(_):
                owner.sleeps += 1
                if owner.sleeps == 2:
                    self.assertIs(owner.running, run)
                    process.returncode = 0
            async def send_log(_):
                owner.reads += 1
                if owner.reads == 1:
                    raise OSError('temporary offline')
            async def noop(*_): pass
            async def wait(): return 0
            process.wait = wait
            run.channel = types.SimpleNamespace(send=noop)
            owner.send_new_log = send_log
            owner.send_failure_evidence = noop
            monitor = bot_method('monitor', {'RunningAgent': object, 'asyncio': types.SimpleNamespace(sleep=sleep), 'SCRIPTS': {'test': ('Test', 'Test')}})
            await monitor(owner, run)
            self.assertGreaterEqual(owner.reads, 3)
            self.assertIsNone(owner.running)
        asyncio.run(scenario())

    def test_failed_log_send_preserves_unsent_lines(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'run.log'
                path.write_text('line one\nline two\n')
                async def fail(*args, **kwargs): raise OSError('offline')
                run = types.SimpleNamespace(log_path=path, announced_lines=0, channel=types.SimpleNamespace(send=fail))
                method = bot_method('send_new_log', {'RunningAgent': object, 'discord_chunks': lambda text: [text], 'discord': types.SimpleNamespace(AllowedMentions=types.SimpleNamespace(none=lambda: None))})
                with self.assertRaises(OSError):
                    await method(types.SimpleNamespace(config={}), run)
                self.assertEqual(0, run.announced_lines)
        asyncio.run(scenario())

    def test_simultaneous_discord_starts_are_serialized(self):
        async def scenario():
            owner = types.SimpleNamespace(start_lock=asyncio.Lock(), running=None, launches=0)
            async def launch(interaction, key, resume):
                if owner.running is not None:
                    return
                await asyncio.sleep(0)
                owner.launches += 1
                owner.running = key
            tree = ast.parse((ROOT / 'discord_bot.py').read_text(encoding='utf-8'))
            method = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'start_script')
            env = {'bot': owner, '_start_script_locked': launch, 'discord': types.SimpleNamespace(Interaction=object)}
            exec(compile(ast.Module(body=[method], type_ignores=[]), '<start-test>', 'exec'), env)
            await asyncio.gather(env['start_script'](None, 'zeleni'), env['start_script'](None, 'trening'))
            self.assertEqual(1, owner.launches)
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
