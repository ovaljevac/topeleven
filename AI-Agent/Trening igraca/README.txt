TOP ELEVEN - PLAYER TRAINING

Run: Pokreni Trening igraca Agent.cmd

Workflow:
1. Home screen -> side menu -> Training -> REPORTS.
2. Select REPEAT on the newest, topmost training session.
3. AI reads the literal FIT percentage from the image, never the color or width of the bar. If the value is below 30%, it opens that player's row.
4. On the profile, AI reads the literal CONDITION percentage and uses a strictly recognized FREE button plus the AI-only ad workflow until the value reaches at least 85%.
5. Close the profile, start training, close the report, and repeat the cycle.

A blue button without the complete FREE label is never clicked.
A delay of 1800 ms is used between clicks (trainingPlayerClickBufferMs in config.json).
After START TRAINING, the agent waits one second and taps the screen once. An additional 1500 ms delay is used before X buttons (trainingPlayerCloseBufferMs).
