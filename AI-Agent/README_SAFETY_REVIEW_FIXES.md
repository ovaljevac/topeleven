# Changes Following the Safety Review

Items 1, 2, 3, 4, 6, and 7 were implemented. Item 5 was not expanded: Campus still waits exactly five seconds after a confirmed return before continuing through the existing path.

- The Training recognizer rejects weak matches and blank images. `IZVJEŠTAJI`, `PONOVI`, the training start control, and the final training X are confirmed by locally matching the reference button appearance rather than by fixed coordinates alone.
- Local return detection for TV/manual, Training, and Alliance Road accepts a previously confirmed transition to Store or Chrome as an alternative to an AI ad screenshot, as Campus already does. Each workflow still requires its own return screen. Re-entering an external app resets the stable-return frame sequence.
- Waiting for Greens or Training offers repeats AI classification even when a blue `BESPLATNO` was previously seen but local validation failed. A transition to gray or to the limit state is therefore not lost inside a separate local wait. An absent button remains an unknown state.
- Campus attempts an alternative slower drag when the strip does not move. Proving the end requires movement in the opposite direction and a return to the same cards, including positions and visual signatures. A stuck strip or lost focus produces an error, not false success.
- Back has a total limit of six attempts per ad context; a new click or restore episode does not reset it. Three consecutive Back attempts without an image change terminate external navigation earlier.
- Hard recovery depends on `Exception.Data['AgentFailureKind']`, including nested exceptions. Message text alone never triggers a restart. `AdTimeout`, `AdCloseFailed`, and `ExternalReturnTimeout` permit the existing hard recovery; `ExternalNavigationStuck`, `ScreenUnknown`, `FocusLost`, and `CampusBoundaryUnknown` do not.

Validation includes reference images, black, white, and random images, a removed X, scaled views, and simulated PowerShell workflows. This does not replace live validation against new ad formats.
