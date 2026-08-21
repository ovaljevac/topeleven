import re
import unittest
from pathlib import Path


MANAGER = Path(__file__).resolve().parents[1] / "TopElevenManager.ps1"


class ManagerLightThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MANAGER.read_text(encoding="utf-8-sig")

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


if __name__ == "__main__":
    unittest.main()
