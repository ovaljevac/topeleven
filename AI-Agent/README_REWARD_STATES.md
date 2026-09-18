# Completion and Restart: Greens and Player Training

Since 2026-09-02, these two workflows distinguish the target offer by both text and color:

| State | Action |
| --- | --- |
| Blue `BESPLATNO` | Validate the button locally and click it. |
| Gray or dark `BESPLATNO` | Require two fresh AI confirmations, pause for 10 seconds, restart the exact BlueStacks instance using the existing process, and reopen the appropriate workflow. |
| `OGRAN. DOSTIGNUTO` | Require two fresh AI confirmations and finish the stage normally. |
| Unknown state, hidden button, or loading dots | Wait. This is never proof of a limit and never a reason to restart. Report an error rather than success after the deadline. |

AI reads only the green-rest offer in the store or the free CONDITION recovery offer in the player profile. Blue MORALE, paid Hire, and navigational FREE controls are not targets. The dedicated AI responses must not contain a click action. Confirmed classifications require confidence of at least 0.90.

Checks are repeated no sooner than every 12 seconds and pass through the existing shared Gemini limiter of at most 15 requests in a rolling 60-second window. These checks are additional to ad-X recognition; the rule requiring one AI confirmation for X is unchanged.

If gray `BESPLATNO` is confirmed again after a successful restart, the restart is repeated without the former one-restart limit. STOP remains available. A restart failure or unrecognized screen still terminates the workflow with an error.

After a restart, the Greens workflow reopens the store. Training reopens `IZVJESTAJI` -> `PONOVI`, reads FIT again, and finds a player below 30%; it does not retain the old player coordinate across a restart. If the limit is confirmed, it does not start the next training session.

Training-cycle safety limits and other deadlines remain errors rather than normal completion caused by exhausted ads. Visual AI classification is not a guarantee of perfect recognition. Automated tests cover response validation and simulated workflows; the real API and game are not part of those tests.
