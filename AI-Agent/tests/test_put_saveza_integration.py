import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PutSavezaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")

    def test_combined_order_is_tv_then_put_saveza_then_campus(self):
        combined = self.script[self.script.index("$combinedStages = @(") :]
        tv = combined.index("Key = 'TV'")
        put_saveza = combined.index("Key = 'PutSaveza'")
        campus = combined.index("Key = 'Kampus'")
        green = combined.index("Key = 'Zeleni'")
        self.assertLess(tv, put_saveza)
        self.assertLess(put_saveza, campus)
        self.assertLess(campus, green)

    def test_all_generic_ad_return_branches_include_put_saveza(self):
        watcher_start = self.script.index("function Watch-TVAdvertisement")
        watcher_end = self.script.index("function Complete-TVManualReward", watcher_start)
        watcher = self.script[watcher_start:watcher_end]
        self.assertIn("'put_saveza'", watcher)
        self.assertGreaterEqual(watcher.count("$ReturnFlow -ne 'tv'"), 3)

    def test_put_saveza_return_uses_two_stable_path_modal_frames(self):
        watcher_start = self.script.index("function Watch-TVAdvertisement")
        watcher_end = self.script.index("function Complete-TVManualReward", watcher_start)
        watcher = self.script[watcher_start:watcher_end]
        branch = watcher[watcher.index("$putSavezaReturnStableCount = 0") :]
        self.assertIn("$ReturnFlow -eq 'put_saveza'", branch)
        self.assertIn("$aiAdVisuallyObserved", branch)
        self.assertIn("Get-PutSavezaFlowSnapshot $Handle", branch)
        self.assertIn("$putSavezaReturn.state -eq 'path'", branch)
        self.assertIn("$putSavezaReturn.closeButton", branch)
        self.assertIn("$putSavezaReturnStableCount -ge 2", branch)
        self.assertIn("return 'top_eleven'", branch)
        self.assertLess(
            branch.index("Get-PutSavezaFlowSnapshot $Handle"),
            branch.index("Test-TopElevenReturnedAfterAd $Handle"),
        )

    def test_confirmed_put_saveza_modal_skips_redundant_main_activity_gate(self):
        flow_start = self.script.index("function Run-PutSavezaAutomation")
        flow_end = self.script.index("function Get-TrainingPlayerFlowSnapshot", flow_start)
        flow = self.script[flow_start:flow_end]
        ad_exit = flow[flow.index("Watch-TVAdvertisement $Handle $false 'put_saveza'") :]
        self.assertIn("$putSavezaAdExit -ne 'top_eleven'", ad_exit)
        self.assertNotIn("Restore-ExternalNavigationBeforeGameAction", ad_exit)

    def test_standalone_mode_launcher_and_config_exist(self):
        self.assertIn("'PutSaveza'", self.script)
        launcher = ROOT / "Put saveza" / "Pokreni Put saveza Agent.cmd"
        self.assertTrue(launcher.is_file())
        self.assertIn("-Mode PutSaveza", launcher.read_text(encoding="utf-8"))
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(config["putSavezaAdButtonWaitSeconds"], 30)

    def test_campus_uses_dynamic_sidebar_target_after_alliance_scroll(self):
        campus_start = self.script.index("function Run-CampusAutomation")
        campus_end = self.script.index("function Invoke-CombinedStage", campus_start)
        campus = self.script[campus_start:campus_end]
        self.assertIn("Find-SideMenuTarget $Handle 'campusButton' 'Up'", campus)
        self.assertNotIn("Click-GameRelative $Handle 0.125 0.420", campus)

    def test_put_saveza_scrolls_down_exactly_once_without_returning_home(self):
        flow_start = self.script.index("function Run-PutSavezaAutomation")
        flow_end = self.script.index("function Run-CampusAutomation", flow_start)
        flow = self.script[flow_start:flow_end]
        self.assertIn(
            "Find-SideMenuTarget $Handle 'allianceButton' 'Down' 'Savezi' 1 1",
            flow,
        )
        self.assertNotIn("Find-SideMenuTarget $Handle 'homeButton' 'Up'", flow)
        self.assertNotIn("Pocetni - Put saveza tok", flow)

    def test_already_complete_requires_positive_loaded_layout(self):
        decision_start = self.script.index("function Wait-PutSavezaAdDecision")
        decision_end = self.script.index("function Wait-PutSavezaStableCloseButton", decision_start)
        decision = self.script[decision_start:decision_end]
        self.assertIn("$snapshot.completedLayout", decision)
        self.assertIn("$snapshot.taskGridLoaded", decision)
        self.assertIn("$null -eq $snapshot.goButtonVisible", decision)
        self.assertIn("$requiredCompleteFrames", decision)


if __name__ == "__main__":
    unittest.main()
