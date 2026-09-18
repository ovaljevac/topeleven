# Resume and Error Screenshots

## Starting a resumed run

- Discord: use `/nastavi skripta:`, then select a stage or `sve`.
- Manager -> Scripts: enable **Nastavi danasnji sacuvani napredak**, then start the selected script.
- Direct launch: run `TopElevenAgent.ps1` with the usual parameters and add `-Resume`.
- The normal `/pokreni` command and the Manager without the resume option begin a new session and create a new progress record. They do not resume automatically.

Restart the Discord bot to load new Discord commands. Reopen the Manager to load its new option.

## Stored state

Progress is stored separately by project, mode, and BlueStacks instance under `%LOCALAPPDATA%\TopElevenAgent\checkpoints`. A record contains the date, configuration fingerprint, completed stages, confirmed rest operations by position, completed training-cycle count, last confirmed step, and a separately recorded action that was started. It does not contain screenshots, API keys, or click coordinates. The previous record is retained as a `.bak` file.

Resume accepts only a record created today with the same configuration. If the record is missing, invalid, or stale, the agent reports an error instead of silently starting over.

Completed stages in `Sve` are skipped. Team Rest skips confirmed positions. Training resumes the cycle count and reads condition again. TV, Campus, and Greens recheck the offers or percentages that are actually available. A started ad or click is not proof that a reward was received.

Before resuming an unfinished stage, the agent verifies the current starting screen. If it cannot be confirmed safely, the agent uses the existing controlled restart of the exact instance and returns to the home screen. It then reaches the unfinished step through normal navigation and fresh validation. This does not restore an old mouse position or resume an instruction in the middle of an ad.

Use resume only with the same account, and do not change the player order between interruption and resuming Team Rest. The record identifies the instance, not the signed-in account or a player by name. An interruption between receiving a reward and saving its completion remains unconfirmed; exactly-once execution cannot be guaranteed across such an interruption.

## Errors and images

Before stage recovery, the agent stores a report next to the log in a `<log>.errors` directory. It contains the stage, last confirmation, expected step, error, and a PNG of the BlueStacks window when capture is available. The same message is not sent again during the same run, and no more than eight reports are created per run.

Discord sends the report and image to the channel from which the script was started, even when the normal live log is disabled. The Manager displays the local report path in its log. The entire desktop is never captured and is not used as a fallback if BlueStacks capture fails. GPU rendering may produce a black image; in that case, the agent sends a text report with the reason and no misleading image.

Images may contain the team name and other data visible in the game. Use a private Discord channel if you do not want to share this information. Reports remain stored locally; old images are not deleted automatically.

STOP is not an error and does not send an image by itself. A temporarily rejected AI suggestion also does not create an image. Reports are created for a stage exception or final error.
