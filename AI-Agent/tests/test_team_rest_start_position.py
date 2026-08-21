import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "TopElevenAgent.ps1").read_text(encoding="utf-8-sig")
WRAPPER = (ROOT / "OdmoriEkipu.ps1").read_text(encoding="utf-8-sig")


def function_body(name, next_name):
    match = re.search(
        rf"function {re.escape(name)} \{{(.*?)function {re.escape(next_name)} \{{",
        SCRIPT,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"Function block {name} was not found")
    return match.group(1)


class TeamRestStartPositionTests(unittest.TestCase):
    def test_queue_preserves_complete_existing_order(self):
        queue_match = re.search(
            r"\$script:TeamRestQueue = @\((.*?)\n\)", SCRIPT, re.DOTALL
        )
        self.assertIsNotNone(queue_match)
        keys = re.findall(r"Key = '([^']+)'", queue_match.group(1))
        self.assertEqual(
            keys,
            [
                "GK", "DL", "DC1", "DC2", "DR", "DMC", "MC1",
                "MC2", "AML", "AMR", "ST", "DL_2", "ST_2",
                "AMR_2", "AML_2",
            ],
        )

    def test_queue_starts_at_selected_item_and_not_at_gk(self):
        body = function_body("Run-TeamRestManualQueue", "Get-TVFlowSnapshot")
        self.assertIn("for ($index = $startIndex;", body)
        self.assertIn("$player = $script:TeamRestQueue[$index]", body)
        self.assertIn("Click-GameRelative $Handle 0.976 $player.Y", body)
        self.assertNotIn("GK plus", body)

    def test_open_team_rest_does_not_click_gk_before_selection(self):
        body = function_body("Open-TeamRest", "Scroll-PlayerList")
        self.assertNotIn("GK plus", body)
        self.assertIn("pocetna pozicija ce biti izabrana iz liste", body)

    def test_rest_window_has_locked_dropdown_and_passes_selection(self):
        self.assertIn("Pocni od pozicije:", SCRIPT)
        self.assertIn("ComboBoxStyle]::DropDownList", SCRIPT)
        self.assertIn("$teamRestStartCombo.Enabled = $false", SCRIPT)
        self.assertIn("$teamRestStartCombo.Enabled = $true", SCRIPT)
        self.assertIn(
            "Run-TeamRestManualQueue $handle $script:TeamRestStartKey", SCRIPT
        )

    def test_cli_wrapper_forwards_start_position(self):
        self.assertIn("[string]$TeamRestStart = 'GK'", WRAPPER)
        self.assertIn("-TeamRestStart $TeamRestStart", WRAPPER)

    def test_ad_return_retries_malformed_ai_json_before_failing_queue(self):
        self.assertIn("$script:VisionMalformedJsonRetryActive", SCRIPT)
        self.assertIn("AI je vratio nepotpun JSON; odmah ponavljam provjeru", SCRIPT)
        body = function_body("Wait-ManualTeamRestAd", "Run-TeamRestManualQueue")
        self.assertIn("Wait-ForAdExitOrControl $Handle 35 $adStartedAt", body)


if __name__ == "__main__":
    unittest.main()
