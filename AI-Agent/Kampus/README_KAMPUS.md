# Top Eleven Campus AI Agent

Run `Pokreni Kampus Agent.cmd` while Top Eleven is open, then click `POKRENI`.

Workflow:

1. Opens the side menu, waits two seconds, clicks `Kampus`, and then waits a three-second safety interval for the screen to load.
2. Confirms Campus and clicks the visually detected left tool icon.
3. Gemini inspects the percentages and selects the name of a building below 100%. A decision that no such buildings remain must still be confirmed by two fresh scans.
4. The Campus camera moves continuously, so an old AI coordinate is never clicked. After the Gemini response, the agent immediately captures a fresh image, projectively aligns the map, and clicks a prevalidated interior point of the selected building. No click occurs unless the alignment, at least three green percentage labels, and a fresh maintenance screen are confirmed. After clicking, the agent verifies that the details panel actually opened and makes another safe attempt when needed, up to three attempts.
5. In the building details, waits up to 180 seconds for the blue button to genuinely contain the white `100%` text. A blue background alone is insufficient.
6. Starts the ad with the same AI-only and Google Play flow. Gemini regularly checks ad controls every 20.5 seconds, while the wake mechanism may request an immediate additional check when necessary.
7. After a confirmed return to Top Eleven, clicks the safe area below the booster to close the details panel.
8. Repeats until two fresh Gemini checks confirm that every visible building is at 100%.

During AI capture and clicking, the agent window is temporarily placed behind BlueStacks so it cannot cover a building. The safety limit is 12 buildings per run. Campus opening time is configured with `campusOpenBufferMs`, details waiting with `campusDetailOpenWaitSeconds`, retry count with `campusBuildingClickAttempts`, and the `100%` wait with `campusHundredButtonWaitSeconds` in the parent `config.json`. Campus alignment operates only on the map, without a fixed universal coordinate offset, and fails closed: if transformation quality is insufficient, the agent does not click.
