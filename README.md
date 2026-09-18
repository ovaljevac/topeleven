# Top Eleven AI Agent

A Windows automation tool for handling everyday tasks in **Top Eleven** running through **BlueStacks**. The agent combines a controlled PowerShell state machine, local OpenCV analysis, and vision AI to recognize the current screen, perform approved actions, and safely process rewarded ads.

> [!IMPORTANT]
> This project controls the mouse and the BlueStacks window. On your first run, start with a single short workflow and supervise its behavior before using **Pokreni sve** (Run All).

## Features

| Workflow | Purpose |
| --- | --- |
| **Uzmi 25 zelenih** | Collects available free green boosters. |
| **Odmori ekipu** | Restores players in order, starting from a selected position. |
| **Top Eleven TV** | Collects TV rewards and completes the manual reward flow. |
| **Mourinho** | Starts and completes the Mourinho rewarded ad. |
| **Kampus** | Processes Campus buildings that have not yet reached 100%. |
| **Put saveza** | Completes the daily video task in Alliance Road. |
| **Trening igrača** | Repeats training and restores player condition when required. |
| **Pokreni sve** | Runs Mourinho, TV, Alliance Road, Campus, and 25 Greens in sequence. |

The central Manager provides workflow selection, a shared log, safe stopping, session resume, a selectable starting stage for the combined workflow, and a selectable starting position for team rest.

## Requirements

- Windows 10 or 11
- BlueStacks with Top Eleven installed and signed in
- Windows PowerShell 5.1
- Python 3 for vision components, tests, and the Discord bot
- A Gemini API key for the default AI configuration

By default, the agent looks for a window titled `BlueStacks App Player`. If your installation uses a different title, update `windowTitle` in `AI-Agent/config.json`.

## Quick start

1. Clone or download the project.
2. Open PowerShell in the `AI-Agent` directory and create a Python environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
   ```

3. Run `AI-Agent\Postavi Gemini API kljuc.cmd` and enter your Gemini API key. The key is stored locally in `AI-Agent/.env`, which is excluded from Git.
4. Run `AI-Agent\Testiraj Gemini.cmd` to verify the connection.
5. Open BlueStacks and Top Eleven, then launch:

   ```text
   AI-Agent\Pokreni AI Agent.cmd
   ```

6. In the Manager, select a short workflow first, click **POKRENI AGENTA**, and monitor the log.

To create a Desktop shortcut, run `Napravi desktop precicu.ps1`. The shortcut opens the central Manager directly.

## How it works

1. `TopElevenManager.ps1` displays the user interface and starts the selected workflow.
2. `TopElevenAgent.ps1` runs the state machine and permits only predefined actions.
3. `VisionAgent.py` captures only the BlueStacks window and requests structured image analysis from the selected vision provider.
4. `XDetector.py` recognizes known screens locally and validates visual details with OpenCV.
5. The agent clicks only after the result passes the checks required for the current step.

For controls inside ads, AI may propose only approved actions such as closing, skipping, or returning from Google Play. OpenCV does not independently choose ad controls. Install, purchase, and payment buttons are never permitted.

If a screen cannot be recognized with sufficient confidence, the agent stays on the same step and repeats the check instead of clicking blindly. A full restart of the appropriate BlueStacks instance is used only in controlled recovery scenarios.

## AI configuration

The default provider is configured in `AI-Agent/ai_config.json`:

```json
{
  "provider": "gemini",
  "model": "gemini-3.5-flash-lite",
  "minimumConfidence": 0.85
}
```

You can add a backup Gemini key by running `AI-Agent\Postavi rezervni Gemini API kljuc.cmd`. If the primary key reaches its quota limit, the agent can switch to the backup key.

### Local Ollama provider

For local processing, install Ollama and download a vision model, for example:

```powershell
ollama pull qwen3-vl:2b
```

Then update `AI-Agent/ai_config.json`:

```json
{
  "provider": "ollama",
  "endpoint": "http://127.0.0.1:11434/api/chat",
  "model": "qwen3-vl:2b",
  "timeoutSeconds": 120
}
```

Gemini requires screenshots of the BlueStacks window to be sent to Google's API. Ollama processes them locally on your computer.

## Configuration files

- `AI-Agent/config.json` — BlueStacks window title, timeouts, delays, retry limits, and workflow parameters.
- `AI-Agent/ai_config.json` — AI provider, model, endpoint, confidence threshold, rate limit, and debug settings.
- `AI-Agent/.env` — local API keys; excluded from Git.
- `AI-Agent/discord_config.json` — local Discord token and authorized users; excluded from Git.

Back up the configuration before making significant changes. Incorrect timeout or coordinate settings may make the automation unreliable.

## Project validation

The easiest option is to open **Postavke** (Settings) in the Manager and select **Provjeri projekat** (Validate Project), or run `AI-Agent\Provjeri projekat.cmd`.

Validation does not control BlueStacks. It checks required files, PowerShell and JSON syntax, Python tests, and the built-in self-tests. To run it from the command line without a graphical dialog:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\AI-Agent\Provjeri projekat.ps1" -NoGui
```

Validation reports and runtime logs are stored in `%LOCALAPPDATA%\TopElevenAgent\logs`.

Individual development checks, run from the `AI-Agent` directory, are:

```powershell
python -m py_compile .\VisionAgent.py .\XDetector.py
python -m unittest discover -s .\tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenManager.ps1 -SelfTest
```

## Discord control (optional)

The agent can be started remotely through a restricted set of Discord slash commands. The bot does not accept arbitrary terminal commands and permits only one active agent at a time.

1. Install the dependencies from `requirements.txt`.
2. Run `AI-Agent\Postavi Discord Bot.cmd` and enter the bot token, Server ID, and your User ID.
3. Run `AI-Agent\Pokreni Discord Bot.cmd` and keep its window open.

Detailed setup instructions and the available commands are listed in the [Discord documentation](AI-Agent/README_DISCORD.md).

## Project structure

```text
topeleven/
├── README.md                         # Main documentation
├── Napravi desktop precicu.ps1       # Creates a Desktop shortcut
└── AI-Agent/
    ├── Pokreni AI Agent.cmd          # Main application entry point
    ├── TopElevenManager.ps1           # Graphical Manager
    ├── TopElevenAgent.ps1             # Automation and state machine
    ├── VisionAgent.py                 # Vision AI communication
    ├── XDetector.py                   # Local OpenCV analysis
    ├── agent_artifacts.py             # Runtime artifacts and records
    ├── config.json                    # General configuration
    ├── ai_config.json                 # AI configuration
    ├── requirements.txt               # Python dependencies
    ├── tests/                         # Automated tests
    ├── regression/                    # Screenshot regression runner
    └── */README*                      # Workflow-specific documentation
```

## Troubleshooting

### The Manager cannot find BlueStacks

Make sure BlueStacks is running and its window title matches the `windowTitle` value in `config.json`.

### Python cannot be found

Install a current Python 3 release and enable **Add Python to PATH**, or create a `.venv` by following the Quick start instructions.

### The Gemini test fails

Run the API key setup tool again, check your internet connection, and verify that API quota is available. Never commit the key to a Git-tracked file.

### The agent does not click a button

This usually means that the screen or control could not be confirmed with sufficient confidence. Review the log and debug captures before changing any thresholds. Rejected and unknown AI analyses may be stored in `AI-Agent/debug`.

### An ad opened the Play Store or Chrome

The agent attempts a safe return using the Android Back command and then validates the screen again. If recovery fails, stop the workflow in the Manager and manually return the game to a known screen.

## Additional documentation

- [AI and safety flow details](AI-Agent/README_AI.md)
- [Combined “Pokreni sve” workflow](AI-Agent/README_SVE_REDOM.md)
- [Discord bot](AI-Agent/README_DISCORD.md)
- [Alliance Road](AI-Agent/Put%20saveza/README.md)
- [Campus](AI-Agent/Kampus/README_KAMPUS.md)
- [Mourinho](AI-Agent/Mourinho/README_MOURINHO.md)
- [Top Eleven TV](AI-Agent/za%20TV%20skriptu/README_TV.md)

## Disclaimer

This is an independent personal automation tool and is not an official Nordeus product. Use it responsibly and at your own risk, while respecting the game's rules and the terms of service of all connected services.
