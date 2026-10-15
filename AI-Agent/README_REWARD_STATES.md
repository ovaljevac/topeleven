# Completion and Restart: Greens and Player Training

Since 2026-09-02, these two workflows distinguish the target offer by both text and color:

| State | Action |
| --- | --- |
| Blue `BESPLATNO` | Validate the button locally and click it. |
| Gray or dark `BESPLATNO` | Require two fresh confirmations, pause for 10 seconds, restart the exact BlueStacks instance using the existing process, and reopen the appropriate workflow. |
| `OGRAN. DOSTIGNUTO` | Require two fresh confirmations and finish the stage normally. |
| Unknown state, hidden button, or loading dots | Wait. This is never proof of a limit and never a reason to restart. Report an error rather than success after the deadline. |

Greens uses local image checks for the aligned resource header, the green resource `+`, and the blue `BESPLATNO` offer with its video and green resource icons. It polls every 200 milliseconds and clicks after two fresh matching ready frames and a final pre-click validation. A ready offer does not wait for OCR. Gray and limit labels are read with local Windows OCR on the green offer row, also requiring two consecutive confirmations. A missing OCR result remains unknown. AI is used only for ad controls and external navigation during ads in this workflow.

Training uses AI to read gray and limit states of the free CONDITION recovery offer in the player profile. Blue MORALE, paid Hire, and navigational FREE controls are not targets. The dedicated AI responses must not contain a click action and require confidence of at least 0.90. Training's AI checks repeat no sooner than every 12 seconds through the shared Gemini limiter of at most 15 requests in a rolling 60-second window. The rule requiring one AI confirmation for an ad X is unchanged.

If gray `BESPLATNO` is confirmed again after a successful restart, the restart is repeated without the former one-restart limit. STOP remains available. A restart failure or unrecognized screen still terminates the workflow with an error.

After a restart, the Greens workflow reopens the store. Training reopens `IZVJESTAJI` -> `PONOVI`, reads FIT again, and finds a player below 30%; it does not retain the old player coordinate across a restart. If the limit is confirmed, it does not start the next training session.

Training-cycle safety limits and other deadlines remain errors rather than normal completion caused by exhausted ads. Visual AI classification is not a guarantee of perfect recognition. Automated tests cover response validation and simulated workflows; the real API and game are not part of those tests.
