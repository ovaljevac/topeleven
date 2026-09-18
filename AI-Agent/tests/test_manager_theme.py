import re
import unittest
from pathlib import Path


MANAGER = Path(__file__).resolve().parents[1] / "TopElevenManager.ps1"
KEY_SETUP = Path(__file__).resolve().parents[1] / "Postavi Gemini API kljuc.ps1"
PROJECT_CHECK = Path(__file__).resolve().parents[1] / "Provjeri projekat.ps1"


class ManagerLightThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MANAGER.read_text(encoding="utf-8-sig")
        cls.key_setup_source = KEY_SETUP.read_text(encoding="utf-8-sig")
        cls.project_check_source = PROJECT_CHECK.read_text(encoding="utf-8-sig")

    def test_window_uses_light_surface_and_dark_text(self):
        self.assertIn('Background="#F4F7FB" Foreground="#172033"', self.source)
        self.assertIn('<SolidColorBrush x:Key="CardBrush" Color="#FFFFFF"/>', self.source)
        self.assertIn('<SolidColorBrush x:Key="MutedBrush" Color="#56657A"/>', self.source)

    def test_primary_actions_remain_high_contrast(self):
        primary_buttons = re.findall(
            r'<Button[^>]+Foreground="White"[^>]+Background="#1769E0"',
            self.source,
        )
        self.assertGreaterEqual(len(primary_buttons), 3)

    def test_selected_navigation_and_script_have_visible_highlight(self):
        self.assertIn("'#DDEAFF'", self.source)
        self.assertIn('TargetName="ScriptCard" Property="BorderBrush" Value="#1769E0"', self.source)

    def test_detachable_mini_log_keeps_light_theme_and_live_controls(self):
        self.assertIn('x:Name="MiniLogWindow"', self.source)
        self.assertIn('x:Name="MiniHeaderDragArea"', self.source)
        self.assertIn('$miniLogWindow.DragMove()', self.source)
        self.assertIn('x:Name="MiniLogTextBox"', self.source)
        self.assertIn('x:Name="MiniActiveScriptText"', self.source)
        self.assertIn('x:Name="MiniStop"', self.source)
        self.assertIn('x:Name="MiniLogToggle"', self.source)
        self.assertIn('x:Name="MiniTopmostToggle"', self.source)
        self.assertIn('$miniLogWindow.Topmost = -not $miniLogWindow.Topmost', self.source)
        self.assertIn("'Iznad: DA'", self.source)
        self.assertIn("'Iznad: NE'", self.source)
        self.assertIn('Topmost="True"', self.source)
        self.assertIn('Background="#F4F7FB" Foreground="#172033" FontFamily="Segoe UI"', self.source)

    def test_mini_log_reuses_manager_timer_and_only_keeps_recent_lines(self):
        self.assertIn('Set-MiniLogLines -Lines $lines', self.source)
        self.assertIn('$allLines.Count - 40', self.source)
        self.assertIn('$miniStop.Add_Click({ Request-AgentStop })', self.source)
        self.assertEqual(self.source.count('New-Object System.Windows.Threading.DispatcherTimer'), 1)

    def test_hidden_mini_log_is_closed_with_manager(self):
        self.assertIn('$script:ManagerClosing = $true', self.source)
        self.assertIn('$miniLogWindow.Close()', self.source)
        self.assertNotIn('if ($miniLogWindow.IsVisible) {\n        $miniLogWindow.Close()', self.source)

    def test_partial_success_has_warning_state_instead_of_stopping(self):
        self.assertIn("'Success', 'Warning', 'Error'", self.source)
        self.assertIn("Set-ManagerState 'Zavrseno uz greske' 'Warning'", self.source)
        self.assertNotIn("Set-ManagerState 'Zavrseno uz greske' 'Stopping'", self.source)

    def test_key_setup_atomically_writes_local_dotenv_without_user_secret(self):
        self.assertIn("Join-Path $PSScriptRoot '.env'", self.key_setup_source)
        self.assertIn('[System.IO.File]::Replace(', self.key_setup_source)
        self.assertIn('[System.IO.File]::Move(', self.key_setup_source)
        self.assertIn('[System.Text.UTF8Encoding]::new($false)', self.key_setup_source)
        self.assertNotIn("SetEnvironmentVariable('GEMINI_API_KEY'", self.key_setup_source)

    def test_manager_prevents_stale_environment_from_shadowing_dotenv(self):
        self.assertIn('function Use-LocalDotEnvForChildProcess', self.source)
        self.assertIn('$StartInfo.EnvironmentVariables.Remove($keyName)', self.source)
        self.assertGreaterEqual(
            self.source.count('Use-LocalDotEnvForChildProcess $startInfo'),
            2,
        )

    def test_settings_can_launch_offline_project_check(self):
        self.assertIn('x:Name="ProjectCheck"', self.source)
        self.assertIn('Content="Provjeri projekat"', self.source)
        self.assertIn(
            "Start-HelperScript 'Provjeri projekat.ps1'",
            self.source,
        )
        self.assertIn("Parser]::ParseFile", self.project_check_source)
        self.assertIn("ConvertFrom-Json", self.project_check_source)
        self.assertIn("-m', 'unittest', 'discover'", self.project_check_source)
        self.assertNotIn("--expected-state", self.project_check_source)
        self.assertNotIn("GEMINI_API_KEY", self.project_check_source)


if __name__ == "__main__":
    unittest.main()
