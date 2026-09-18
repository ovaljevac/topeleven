# Complete Top Eleven AI Agent

Run `Pokreni AI Agent.cmd`, select `Pokreni sve`, choose the starting stage, and click `POKRENI AGENTA`. The legacy direct launcher `Pokreni sve redom.cmd` still starts the full sequence from the Mourinho stage.

The sequence is:

1. Mourinho ad.
2. Top Eleven TV ads.
3. Daily Alliance Road ad.
4. Campus buildings below 100%.
5. Collect 25 greens (the `Zeleni` workflow).

When ordinary AI or visual uncertainty occurs, the agent does not close the game. It repeats a safe check at the same step. A hard restart of the exact BlueStacks instance is used only when an ad is confirmed to be stuck or a verified home screen is required before continuing. A failed stage is recorded in the log; after a safe preflight check, the agent proceeds to the next stage, and the Manager reports the result as `Zavrseno uz greske` (Completed with errors). The `ZAUSTAVI` button stops the entire combined workflow.

If an ad opens the Google Play Store or Chrome, the agent sends Android Back through the current BlueStacks ADB connection, returns to the ad, and closes it with its X control. The next stage cannot click anything until `MainPlayerNativeActivity` and the Top Eleven header have been confirmed as stable.

All existing individual launchers continue to work unchanged.
