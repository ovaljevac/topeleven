# Mourinho AI Agent

Run `Pokreni Mourinho Agent.cmd` while Top Eleven is open on the main screen.

Automation flow:

1. Confirms the main screen using `1.png`.
2. Sends the current BlueStacks screenshot to Gemini AI and requests the center of the small square button to the right of the `Nivo spremnosti` progress bar and to the left of `PREGLED UTAKMICE`. The AI location is used without an OpenCV decision about that button, and only coordinates inside the readiness area are allowed.
3. Confirms the Mourinho window using `2.png`.
4. Waits up to 30 seconds for a blue button that must contain a recognizable `POGLEDAJ` label or icon. A plain blue rectangle is not accepted.
5. Starts the ad and uses the same OpenCV plus Gemini AI flow for X, skip, and Google Play as the TV agent.
6. Finishes when three consecutive checks confirm the upper Top Eleven resource bar containing tokens and the green, blue, and red resources. The Mourinho window is not required after the ad.

A safety delay of 1500 ms is used between significant clicks.
