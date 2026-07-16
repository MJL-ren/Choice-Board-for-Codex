# Testing Status

Last checked: 2026-07-16

## Passed locally

- Skill structure validation with the official skill validator.
- Nine Python tests covering schema rejection, safe rendering, strict types, marker-safe labels, and fail-closed activation modes.
- Headless Chrome behavior smoke test covering:
  - required-answer errors and focus movement;
  - `Other` show/hide behavior without deleting typed text;
  - completed submissions versus explanation requests;
  - duplicate-click suppression;
  - failed-send recovery;
  - missing host API fallback;
  - 320px and 736px layouts;
  - computed Codex/Visualize light and dark theme changes.

The browser smoke test uses the installed Visualize stylesheet and an existing local Chrome or Playwright browser. It does not contact an external service or send a real follow-up.

## Still required before release

- One explicitly authorized Codex Desktop Default-mode board and one real `sendFollowUpMessage` submission.
- Unicode and multiline verification in the actual returned conversation message.
- Activation metadata reload behavior after changing `explicit`, `suggest`, or `auto` in an installed copy.
- Whether an untagged natural-language “use a choice board” request is treated as an explicit invocation; until verified, `$codex-choice-board` is the guaranteed call form.
- Packaging and clean-install verification from the repository.

Passing local tests does not claim support for Codex CLI, VS Code, Apps SDK, or MCP surfaces.
