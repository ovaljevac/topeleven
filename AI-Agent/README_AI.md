# Top Eleven AI Vision Agent

This directory contains the active AI-first version of the project. The parent directory contains only the entry-point documentation and the Desktop shortcut tool.

The main entry point is `Pokreni AI Agent.cmd`. It opens the central light-themed dashboard with all scripts, a shared log, and Start/Stop controls. Every module can run independently. `Pokreni sve` allows selection of the starting stage, while Team Rest allows selection of the starting player position. The detachable mini-log has an `Iznad: DA/NE` switch. Disable `Iznad` if the window could cover BlueStacks and appear in an AI screenshot.

Ordinary AI or visual uncertainty does not close Top Eleven. The agent remains on the current step and repeats a safe check. A full restart of the exact BlueStacks instance is used only for a confirmed stuck ad or when a verified home screen is required before the next stage. In the combined workflow, a failed stage is recorded and the agent then proceeds safely to the next stage.

## How it works

1. A PowerShell state machine controls the permitted actions.
2. `VisionAgent.py` captures only the BlueStacks window and sends the diagnostic image to the selected vision provider.
3. The model must return strictly defined JSON.
4. For ad controls, only the AI actions `click_close`, `click_skip`, and `click_google_play`, with coordinates on the original image, are accepted.
5. OpenCV does not propose, confirm, move, or click an ad's X, skip, or Google Play controls.
6. If AI is unavailable or does not see an allowed control, the agent clicks nothing.
7. Google Play and Chrome are recognized only through AI image analysis. ADB is used only to send the Back command, with Escape as a fallback.
8. An accepted AI confirmation of the Top Eleven screen ends ad monitoring. The full local Home and Store screens may be confirmed on two fresh frames. Android activity, dumpsys, and Player.log are not read and do not participate in any decision.

AI never controls the mouse directly. PowerShell accepts only a known action with the appropriate control type and a coordinate inside the original image. `Install`, `Get`, purchase, and payment controls are never clicked, but their presence no longer hides a separate genuine X or skip control and does not block Back from the Store.

## Gemini 3.5 Flash-Lite (currently enabled)

`ai_config.json` uses `gemini-3.5-flash-lite` with the `minimal` thinking level for low latency. Google no longer provides `gemini-2.5-flash` to new API users. In the Manager, open `Postavke` and select `Postavi API kljuc`. The tool atomically stores `GEMINI_API_KEY` in the local `AI-Agent/.env` file without displaying the key or writing it to the log. `.env` is excluded from Git. Verify the setup afterward with `Testiraj Gemini`.

A free-tier key is sufficient until Google's request limits are exceeded. Images are sent to the Google Gemini API. For fully local processing, use the Ollama configuration below.

## Local Ollama model (fallback)

Ollama `0.32.5` is installed on the original development computer. The agent uses the local `qwen3-vl:2b` vision model, approximately 1.9 GB, because the larger 4B model may run out of VRAM while BlueStacks is running on an RX 580. The configuration uses the local API at `http://127.0.0.1:11434/api/chat`.

If the model is removed, download it again:

```powershell
ollama pull qwen3-vl:2b
```

Verify that the service and model are available:

```powershell
ollama list
```

The model, endpoint, and safety thresholds are configured in `ai_config.json`. To disable AI temporarily without changing code, set `enabled` to `false`.

To switch back to the local model, set:

```json
"provider": "ollama",
"endpoint": "http://127.0.0.1:11434/api/chat",
"model": "qwen3-vl:2b",
"timeoutSeconds": 120
```

The first X detection begins 12 seconds after an ad starts. The model is loaded in the background as soon as `POKRENI` is clicked.

Long interactive ads use a wake mechanism. After 75 seconds without an exit, the agent taps a neutral ad area every 12 seconds and immediately captures an AI screenshot without an additional wait. This attempts to reveal Google Play or skip controls that appear only briefly. Configure this behavior with `adWakeTapAfterSeconds`, `adWakeTapIntervalSeconds`, and `adWakeTapMaximum` in `config.json`.

Ad controls are semantically AI-only: Gemini, using the clean original BlueStacks image, is the sole component that decides whether a control is X, >>/skip, or Google Play/Play Store. OpenCV may not independently propose another button or initiate a click. For X only, it may validate the diagonals within a small area around the AI point and return their actual center. There is no universal coordinate offset.

For X, AI remains the sole component that decides which control closes the ad. After that decision, the agent captures a fresh image and attempts to geometrically center the two diagonals of the same X only within a small area around the proposed point. Local analysis may not search for another button or apply a fixed offset. One AI decision is sufficient when the fresh local frame confirms the diagonals and their center; the X is then clicked immediately without a second Gemini request. An AI coordinate without locally detected diagonals remains only a candidate and cannot authorize a click by itself.

The first AI check begins 12 seconds after the ad starts, followed by regular Gemini calls every 12 seconds through `aiProbeIntervalSeconds`. An X locally confirmed from that one check is immediately ready to click. After a click or candidate loss, the pre-click flow begins actual monitoring for a return or new controls. A confirmed return ends the ad immediately, while a newly and locally confirmed X is used in the same iteration. If monitoring remains inconclusive, the next attempt waits for the regular interval. Used coordinates are cleared before monitoring. A wake check also uses a confirmed return immediately instead of discarding it. A wake tap during a long interactive ad may initiate an extra AI check, subject to the existing API limits.

Returning from a Google Play or Chrome flow uses a fresh AI confirmation before Back and a new AI image afterward. The number of Back commands is limited, and an unchanged screen stops the sequence. Android activity checks have been removed completely from stage startup, ad startup, monitoring, Training, and recovery. ADB serves only as a command channel, not as a screen-recognition source.

The `PRIRUCNIK` TV reward has its own safe exit path. After an ad has already been observed, two consecutive local `manual_3` frames showing `NABAVLJEN NOVI PRIRUCNIK` immediately hand the workflow to manual processing. A delayed Android activity record can therefore no longer leave the agent inside the ad loop after the reward has already been won.

After an ad has been observed, an ordinary TV reward accepts two consecutive local `tv` frames as a return even when Android activity data is delayed after the Play Store. This path is forbidden for the `PRIRUCNIK` reward, which must show the dedicated `manual_3` screen.

Fast local return confirmations for `tv`, `manual_3`, and the player profile activate only after AI has genuinely seen an ad screen on a previous fresh frame. ADB `AdActivity` alone is insufficient because the old game screen may remain visible during the first seconds of a new activity. In addition to two stable frames, the player profile must show its strict visual signature: a large light modal with aligned red `POVREDE`, blue `MORAL`, and green `KONDICIJA` controls. The resource header is not required because the profile may partly cover it.

After an AI-confirmed ad, Alliance Road accepts a return when two consecutive local `alliance_flow` frames see the same `path` modal and a stable modal X. This already confirmed modal does not pass through an additional 75-second `MainPlayerNativeActivity` gate. It is immediately handed to the existing stable-X validation and closed.

Before a stage begins, an old ADB or Player.log `AdActivity` record cannot start the ad watcher by itself. If two consecutive local TV-flow frames clearly identify a full `POCETNI` screen, the record is treated as stale and the stage continues without inventing an ad. An actual Store or Chrome foreground screen still has priority and must be closed first.

If Gemini returns truncated or incomplete JSON once while confirming a return, the agent immediately repeats the analysis using a fresh image. In Team Rest, enough time is allowed after clicking X for another check following API backoff, so one malformed response no longer terminates the entire player sequence after the ad has already closed.

If Gemini returns coordinates in its own 0–1000 spatial scale despite the 0–1 schema, for example `26,94`, the AI-only validator automatically converts them to `0.026,0.094` instead of rejecting the detected X. Literal pixel coordinates are also supported as a fallback.

During `Odmori ekipu`, a blue background alone is not proof that the rewarded button is ready. The local recognizer must see the complete white `BESPLATNO` label spread across the button in the real Top Eleven window. Loading dots and an empty blue button are rejected. The label must remain at the same location over two checks spanning at least 350 ms, followed by one more fresh check immediately before clicking. The click uses the detected button center without a fixed offset. Afterward, the agent separately confirms that the ad started, and another click is forbidden for eight seconds. If the stable label returns or loading continues, the agent resumes safe waiting instead of starting X monitoring too early.

The `Odmori ekipu` window contains a `Pocni od pozicije` list. The selected item is the first player processed; earlier items are skipped, and the agent continues in the existing order through the end, including second-round entries. The same option is available from the command line, for example `OdmoriEkipu.ps1 -TeamRestStart AMR`.

In the Campus workflow, one valid AI building selection with a parseable `TARGET` name and a percentage below 100% proceeds directly to a click. The local Campus recognizer must then confirm that details opened with a genuine blue `100%` reward area; an arbitrary details screen is insufficient. Multiple buildings with the same percentage therefore cannot stall confirmation at `1/2`. A decision that no buildings remain still requires two fresh AI confirmations. If the click misses or opens a building without that reward area, details are closed and all previous missed points are marked with red crossed circles on the next AI image and forbidden on the next attempt. The click continues to use a fresh direct AI coordinate without a universal offset.

The Alliance Road workflow uses local visual anchors only for Top Eleven navigation. It locates the `Savezi` row, the `PUT SAVEZA` tile, the correct blue video `IDI`, and the modal X. Green `IDI` buttons are rejected. The blue `IDI` must contain the video icon and complete text across two stable checks, followed by another fresh check immediately before clicking. A blue background or loading state alone is insufficient. The ad then uses the same AI-only X, skip, and Google Play monitoring as other workflows.

After opening the side menu, Alliance Road performs exactly one downward wheel step and then searches for `Savezi`. If the row is not recognized, the workflow stops safely instead of scrolling ten times.

## Running the agent

For automated repetition of the latest training session, use `Trening igraca\Pokreni Trening igraca Agent.cmd`. The workflow checks the selected player's condition, uses the complete `BESPLATNO` text and the existing AI-only ad monitor until the player reaches at least 85%, then starts training and repeats the cycle.

Open BlueStacks and Top Eleven first, then run:

```text
Pokreni AI Agent.cmd
```

Use the Calibration option to validate coordinates safely. Calibration does not click.

## Offline validation

After opening the first Campus building, the workflow remains in the details view and selects subsequent buildings from the lower-left strip. Full green indicators are skipped, while fully visible cards with a white remainder are selected after fresh local validation. The strip is first moved to its left edge and is then dragged from right to left for later buildings. Completion requires two attempts with no movement at the right edge and no visible incomplete cards. An ad starts only from a confirmed blue video `100%` button, never from the paid `+10%` or `UNAPRIJEDI` controls.

The easiest validation method is to open `Postavke` in the Manager and click `Provjeri projekat`, or run `Provjeri projekat.cmd`. Validation does not control BlueStacks. It checks required files, PowerShell and JSON syntax, Python tests, and both self-tests. To run it without dialogs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Provjeri projekat.ps1" -NoGui
```

If the computer does not have the bundled Codex Python runtime, create a `.venv` or `venv` and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Individual checks are:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenManager.ps1 -SelfTest
python -m unittest discover -s .\tests -v
python -m py_compile .\VisionAgent.py .\XDetector.py
python .\regression\run_opencv_regression.py --zip "C:\path\to\ss.zip"
```

The regression runner reads screenshots directly from the specified `ss.zip`; it does not extract files into the project or modify the archive. If the archive is absent, full validation clearly marks this optional check as skipped.

Do not enable the complete automated sequence before testing one ad under supervision. Rejected and unknown AI results are stored in the `debug` directory for later analysis. At most `maximumDebugCaptures` captures, 200 by default, are retained together with their JSON metadata.

## Backup Gemini API key

Run `Postavi rezervni Gemini API kljuc.cmd` to enter a second key. When Gemini returns HTTP 429 because the quota is exhausted, VisionAgent automatically switches to the next configured key. The backup key should belong to a different Google Cloud project with its own available quota; keys from the same project share the limit.
