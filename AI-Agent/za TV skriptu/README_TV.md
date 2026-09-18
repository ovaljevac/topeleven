# Top Eleven TV AI Agent

Start Top Eleven and leave it on the home screen as shown in `1.png`. Then double-click `Pokreni TV Agent.cmd` and click `POKRENI`.

Workflow:

1. Opens the side menu, waits two seconds, clicks `Pocetni`, and waits another two seconds.
2. Confirms the home screen, visually locates the white monitor/play TV icon in the upper bar, and clicks its actual center. It does not use a fixed X coordinate because the width of the resource numbers moves the TV button.
3. On the TV screen, accepts a button only when it sees both the appropriate blue rectangle and a white icon or `POGLEDAJ` text pattern. Blue color alone is insufficient. Buttons are processed from left to right.
4. Ads use the same fully AI-only workflow as the main agent: the first regular Gemini check occurs after 20.5 seconds, followed by checks every 20.5 seconds, while a wake tap may request an immediate additional check when necessary.
5. For `PRIRUCNIK`, confirms screens 3, 4, and 5, performs two individual taps, and then clicks `NASTAVI`. The dynamic detector recognizes a green button with real white text whether it occupies part or nearly all of the width; the existing reference coordinate remains a secondary recognizer and fallback.
6. Stops only after at least 30 uninterrupted seconds without an available `POGLEDAJ` button. Any valid button resets this timer through `tvWatchButtonWaitSeconds` in the parent `config.json`.

A delay of 2000 ms (`tvNavigationBufferMs`) is used between the initial side-menu and `Pocetni` clicks. Other navigation clicks use 1500 ms (`tvClickBufferMs`), with additional waiting until the detector confirms the next screen.

References `1.png` through `5.png` remain in this directory and are used only for local screen classification.
