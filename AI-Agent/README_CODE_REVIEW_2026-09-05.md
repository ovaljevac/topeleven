# Code Review — September 5, 2026

The review covered ad loops, initial screen validation, Training, cancellation, AI validation, Discord startup and monitoring, progress persistence, error reports, and the Manager. This was a review of specific paths and regressions, not a guarantee that every possible failure has been eliminated.

## Fixes from this review

- Team Rest and the shared ad workflow now use the wake-check result in the same iteration. They do not send a new AI analysis that would discard the return or ad control that was just confirmed. Greens also retains wake results for skip and Google Play.
- Training first waits locally for the screen and checks for the disconnected-session popup after five seconds. Subsequent attempts are spaced out, so normal short transitions do not consume an extra AI request.
- After a restart caused by a gray `BESPLATNO`, Training continues condition recovery through `IZVJESTAJI` and `PONOVI`. It does not attempt to start training again before resuming that recovery. A recognized limit finishes the stage.
- User cancellation during an AI request is propagated as cancellation instead of being reported as an AI provider failure.
- Both base click functions reject NaN, infinite values, and coordinates outside the 0–1 range before any side effects.
- An AI response with an incorrect action, screen, or control type returns validation errors instead of throwing an exception. A textual `topElevenReturned` value is not accepted as a Boolean return confirmation.
- Discord serializes simultaneous start requests, begins monitoring before sending confirmation, and defers the interaction response while starting the process.
- A temporary Discord log-send failure does not remove the active process from monitoring. Unsent lines remain available for the next attempt. If a multi-block send partly succeeds, a previously sent block may be repeated.
- A metadata file disappearing while reports are being read does not terminate the reader.
- Initial AI validation preserves the check identity across retries, enabling multiple consecutive confirmations when the configuration requires them.

## Validation and limitations

The complete unittest suite was run, including tests using reference images and simulated PowerShell workflows. Additional simulations cover invalid AI JSON, request cancellation, the Training popup, wake return, invalid coordinates, Discord network interruption, and concurrent startup. An outdated Training resume test was updated to simulate the real `UMORNI IGRACI` dialog and to prohibit a new training start after restart until recovery is complete.

The PowerShell files pass parsing. The Agent and Manager pass SelfTest, but Agent SelfTest currently does not find a visible window for the configured BlueStacks instance or an ADB serial. Therefore, clicks, Gemini requests, and Discord delivery were not validated live. The optional `ss.zip` archive is unavailable; local reference-image tests are included.

Restart the agent and Discord bot to load the changes.
