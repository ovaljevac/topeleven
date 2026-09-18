import ast
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from test_team_rest_free_button import function_body

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_artifacts import read_failure_events, failure_caption


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows required')
class PersistenceTests(unittest.TestCase):
    def run_ps(self, assertions):
        with tempfile.TemporaryDirectory() as directory:
            quote = lambda s: "'" + str(s).replace("'", "''") + "'"
            source = (ROOT / 'AgentPersistence.ps1').read_text(encoding='utf-8')
            source = source.replace("[Environment]::GetFolderPath('LocalApplicationData')", quote(directory)).replace('$PSScriptRoot', quote(ROOT))
            prefix = """
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
function Add-Log { param($Message); Write-Host $Message }
function Test-Cancelled {}
$script:Mode='Sve'; $script:BlueStacksInstance='TestInstance'
$script:CombinedStartStage='Mourinho'; $script:TeamRestStartKey='GK'
$script:TeamRestQueue=@([PSCustomObject]@{Key='GK'})
"""
            result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command', prefix+source+'\n'+assertions], capture_output=True, text=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stdout+result.stderr)

    def test_round_trip_and_new_run_does_not_resume_implicitly(self):
        self.run_ps("""
Initialize-AgentCheckpoint $false
$script:Checkpoint.CompletedStages=@('Mourinho')
$script:Checkpoint.TrainingCycles=3
Set-AgentCheckpointStep 'training_cycle_confirmed:3'
Set-AgentPendingAction 'open next report'
Initialize-AgentCheckpoint $true
if ($script:Checkpoint.TrainingCycles -ne 3 -or $script:Checkpoint.CompletedStages[0] -ne 'Mourinho' -or -not $script:ResumeNeedsPreparation) { throw 'lost progress' }
if ($script:Checkpoint.Step -ne 'training_cycle_confirmed:3' -or $script:Checkpoint.PendingAction -ne 'open next report') { throw 'confirmed and pending mixed' }
Initialize-AgentCheckpoint $false
if (@($script:Checkpoint.CompletedStages).Count -ne 0 -or $script:ResumeNeedsPreparation) { throw 'new run resumed silently' }
""")

    def test_old_day_wrong_config_and_bad_player_are_rejected(self):
        self.run_ps("""
foreach ($case in @('day','config','player')) {
    Initialize-AgentCheckpoint $false
    switch ($case) {
        'day' {$script:Checkpoint.Day='2001-01-01'}
        'config' {$script:Checkpoint.ConfigHash='wrong'}
        'player' {$script:Checkpoint.CompletedPlayers=@('not-a-player')}
    }
    Save-AgentCheckpoint
    $caught=$false
    try { Initialize-AgentCheckpoint $true } catch {$caught=$true}
    if (-not $caught) { throw 'unsafe checkpoint accepted' }
}
""")

    def test_missing_checkpoint_does_not_start_fresh(self):
        self.run_ps("$caught=$false; try { Initialize-AgentCheckpoint $true } catch {$caught=$true}; if (-not $caught) {throw 'missing checkpoint silently ignored'}")

    def test_resume_keeps_current_screen_without_generic_loaded_check(self):
        self.run_ps("""
function Test-TopElevenReturnedAfterAd { throw 'generic loaded check must not run' }
function Test-GameHomeLoaded { throw 'home check must not run' }
function Restart-TopElevenForStageRetry { throw 'resume must not restart current game screen' }
$script:ResumeNeedsPreparation=$true
if ((Prepare-AgentResume ([IntPtr]1)) -ne [IntPtr]1) {throw 'current handle was replaced'}
if ($script:ResumeNeedsPreparation) {throw 'resume preparation flag was not cleared'}
""")

    def test_missing_window_publishes_text_report_without_desktop_capture(self):
        self.run_ps("""
Initialize-AgentCheckpoint $false
function Get-BlueStacksWindow { return [IntPtr]::Zero }
$script:ExternalLogPath=Join-Path (Split-Path $script:CheckpointPath) 'test.log'
$script:LastStatusText='Waiting for blue button'
$failure=[System.Exception]::new('button unavailable')
Save-AgentFailureEvidence 'Kampus' $failure
Save-AgentFailureEvidence 'Kampus' $failure
$files=@(Get-ChildItem -LiteralPath "$($script:ExternalLogPath).errors" -Filter '*.json')
if ($files.Count -ne 1) {throw 'duplicate or missing event'}
$event=Get-Content -Raw -LiteralPath $files[0].FullName | ConvertFrom-Json
if ($event.Captured -or $event.Expected -ne 'Waiting for blue button') {throw 'invalid evidence'}
""")

    def test_completed_phase_is_skipped_before_any_screen_action(self):
        agent = (ROOT / 'TopElevenAgent.ps1').read_text(encoding='utf-8-sig')
        definition = 'function Invoke-StageWithRecovery {' + function_body(agent,'Invoke-StageWithRecovery') + '}\n'
        self.run_ps(definition+"""
Initialize-AgentCheckpoint $false
$script:Checkpoint.CompletedStages=@('Kampus')
function Get-BlueStacksWindow {throw 'must not touch window'}
$result=Invoke-StageWithRecovery 'Kampus' ([IntPtr]1) {throw 'must not replay'}
if (-not $result.Success -or $result.Attempts -ne 0) {throw 'did not skip completed phase'}
""")

    def test_window_capture_success_and_black_frame_fallback(self):
        self.run_ps("""
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition 'public class Win32Agent { public static bool Paint = true; public static bool PrintWindow(System.IntPtr h, System.IntPtr dc, uint flags) { if (Paint) { using (var g = System.Drawing.Graphics.FromHdc(dc)) {g.Clear(System.Drawing.Color.White);} } return true; } }'
Initialize-AgentCheckpoint $false
function Get-BlueStacksWindow { return [IntPtr]1 }
function Get-WindowRectangle { return [PSCustomObject]@{Left=0;Top=0;Right=80;Bottom=60} }
$script:ExternalLogPath=Join-Path (Split-Path $script:CheckpointPath) 'capture.log'
Save-AgentFailureEvidence 'TV' ([System.Exception]::new('first'))
[Win32Agent]::Paint=$false
Save-AgentFailureEvidence 'TV' ([System.Exception]::new('second'))
$files=@(Get-ChildItem -LiteralPath "$($script:ExternalLogPath).errors" -Filter '*.json')
$events=@($files | ForEach-Object {Get-Content -Raw -LiteralPath $_.FullName | ConvertFrom-Json})
if (@($events | Where-Object {$_.Captured}).Count -ne 1 -or @($events | Where-Object {-not $_.Captured}).Count -ne 1) {throw 'capture/black fallback failed'}
$images=@(Get-ChildItem -LiteralPath "$($script:ExternalLogPath).errors" -Filter '*.png')
if ($images.Count -ne 1) {throw 'blank image published'}
$image=[Drawing.Image]::FromFile($images[0].FullName)
try {if ($image.Width -ne 80 -or $image.Height -ne 60) {throw 'capture included desktop'}} finally {$image.Dispose()}
""")


class ArtifactTests(unittest.TestCase):
    def test_only_run_owned_png_is_selected_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory)/'run.log'
            folder = Path(str(log)+'.errors'); folder.mkdir()
            event_id = 'a'*32
            (folder/(event_id+'.json')).write_text(json.dumps({'Version':1,'Captured':True,'imagePath':'C:/secret.txt'}))
            image = folder/(event_id+'.png'); image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
            events = read_failure_events(log,set())
            self.assertEqual(image, events[0][2])
            self.assertEqual([], read_failure_events(log,{event_id}))
            image.write_bytes(b'not a PNG')
            self.assertIsNone(read_failure_events(log,set())[0][2])

    def test_invalid_metadata_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory)/'run.log'; folder=Path(str(log)+'.errors'); folder.mkdir()
            (folder/('b'*32+'.json')).write_text('incomplete {')
            self.assertEqual([], read_failure_events(log,set()))

    def test_discord_sender_attaches_image_without_importing_or_starting_bot(self):
        tree = ast.parse((ROOT/'discord_bot.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TopElevenBot')
        method=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='send_failure_evidence')
        sent=[]; attachments=[]
        class Attachment:
            def __init__(self,*args,**kwargs): self.closed=False; attachments.append(self)
            def close(self): self.closed=True
        class HTTPError(Exception): pass
        class Channel:
            async def send(self,*args,**kwargs): sent.append((args,kwargs))
        env={'read_failure_events':lambda *_:[('a',{'Stage':'Kampus'},Path('example.png'))],
             'failure_caption':failure_caption,'RunningAgent':object,
             'discord':types.SimpleNamespace(File=Attachment,HTTPException=HTTPError,AllowedMentions=types.SimpleNamespace(none=lambda:None))}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<sender>','exec'),env)
        run=types.SimpleNamespace(log_path=Path('run.log'),announced_errors=set(),channel=Channel())
        asyncio.run(env['send_failure_evidence'](None,run))
        self.assertIn('file',sent[0][1]); self.assertTrue(attachments[0].closed)
        self.assertEqual({'a'},run.announced_errors)

    def test_resume_command_and_manager_option_are_wired(self):
        bot=(ROOT/'discord_bot.py').read_text(encoding='utf-8')
        manager=(ROOT/'TopElevenManager.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('name="nastavi"',bot)
        self.assertIn('resume=True',bot)
        self.assertIn('(["-Resume"] if resume else [])',bot)
        self.assertIn('ResumeCheck',manager)
        self.assertIn('-Resume:([bool]$resumeCheck.IsChecked)',manager)


if __name__=='__main__': unittest.main()
