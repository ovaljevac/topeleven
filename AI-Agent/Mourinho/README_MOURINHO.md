# Mourinho AI Agent

Run `Pokreni Mourinho Agent.cmd` while Top Eleven is open on the main screen.

Automation flow:

1. Recognizes both the earlier main screen (`1.png`) and the redesigned one (`3.png`).
2. Locates the small Mourinho button to the right of `Nivo spremnosti` directly with OpenCV. On the redesigned screen this is the gray `i` button at the right end of the readiness bar near the bottom edge; purple badges beside the team crests are explicitly excluded. Older red/yellow warning buttons remain supported. Gemini AI is used only as a fallback, and the large `PREGLED UTAKMICE` button is explicitly excluded.
3. Confirms either version of the Mourinho window using `2.png` or `4.png`.
4. Waits up to 30 seconds for a blue button that must contain a recognizable `POGLEDAJ` label or icon. A plain blue rectangle is not accepted.
5. Starts the ad and uses the same OpenCV plus Gemini AI flow for X, skip, and Google Play as the TV agent.
6. Finishes when three consecutive checks confirm the upper Top Eleven resource bar containing tokens and the green, blue, and red resources. The Mourinho window is not required after the ad.

A safety delay of 1500 ms is used between significant clicks.
