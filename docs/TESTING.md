# Testing Status

Last checked: 2026-07-16

Live Codex Desktop findings and the current edge-path test plan are recorded in [`LIVE_TEST_FINDINGS_2026-07-16.md`](LIVE_TEST_FINDINGS_2026-07-16.md).

## Passed locally

- Skill structure validation with the official skill validator.
- Twelve Python tests covering schema rejection, safe rendering, strict types, marker-safe labels, initial-draft validation, and fail-closed activation modes.
- Headless Chrome behavior smoke test covering:
  - required-answer errors and focus movement;
  - `Other` show/hide behavior without deleting typed text;
  - completed submissions versus explanation requests, including readable draft summaries;
  - duplicate-click suppression while one host request is in flight;
  - fulfilled-but-unconfirmed, thrown-error, and `{ isError: true }` recovery;
  - byte-identical retry with stable `submission_id`, plus a new ID after edits;
  - restored radio, checkbox, text, and Other draft values without focus theft;
  - missing host API fallback;
  - 320px and 736px layouts;
  - computed Codex/Visualize light and dark theme changes.

The browser smoke test uses the installed Visualize stylesheet and an existing local Chrome or Playwright browser. It does not contact an external service or send a real follow-up.

## Still required before release

- One explicitly authorized Codex Desktop recheck of cancellation, unconfirmed retry, readable explanation draft, callback delivery, and restored replacement board.
- Activation metadata reload behavior after changing `explicit`, `suggest`, or `auto` in an installed copy.
- Whether an untagged natural-language “use a choice board” request is treated as an explicit invocation; until verified, `$codex-choice-board` is the guaranteed call form.
- Packaging and clean-install verification from the repository.

## Confirmed live

- Three consecutive ordinary submissions returned to the same conversation with distinct form IDs.
- Korean text, punctuation, single choice, multi choice, optional input, and Unicode survived the returned message.
- Required-answer blocking displayed a question-specific message.
- A cancelled explanation confirmation produced no callback; the old board falsely showed `보냈어요` and locked. This failure is preserved in the findings note and is the reason for the new unconfirmed/retry contract.

Passing local tests does not claim support for Codex CLI, VS Code, Apps SDK, or MCP surfaces.
