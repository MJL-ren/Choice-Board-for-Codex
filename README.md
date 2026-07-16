# Choice Board for Codex

> Unofficial community project. Not affiliated with or endorsed by OpenAI.

Ask several related questions in one lightweight Codex Desktop board. People can choose one answer, select several, type their own answer, or ask for more explanation before deciding. The board requests a response in the same conversation and validates the envelope that actually arrives. No MCP required.

## Status

Working private live prototype. Three ordinary Codex Desktop submissions have returned successfully. A cancellation and explanation-resume failure was reproduced, fixed locally, and still needs one live recovery recheck before release.

## Designed for ordinary use

- Uses plain-language labels instead of exposing HTML or a schema.
- Adds an **Other** path to choice questions by default.
- Adds **I need more explanation** before the user has to commit to an answer.
- Shows a short readable answer summary before the compact machine payload.
- Uses Codex/Visualize native controls and is designed to follow the host light or dark theme.

## When it appears

The safe default is **only when called directly**. A user can later ask the skill to change to either:

- **Ask first** when a choice board would help.
- **Open automatically** when several related answers are easier to collect visually.

Missing or damaged settings always fall back to direct invocation only. Automatic use is still excluded for secrets, sensitive data, and final approval of destructive or external actions.

The setting is meant to be changed in ordinary language through the skill, for example: “Use `$codex-choice-board` only when I call it,” “ask me first when it would help,” or “open it automatically when it fits.” No YAML or JSON editing is expected from the user.

## Intended V0

- Render one thread-scoped board in Codex Desktop.
- Support `single`, `multi`, and `text` questions.
- Offer `Other` and a board-level explanation request by default.
- Validate required answers before submission.
- Request one self-identifying follow-up message in the current conversation without pretending that a closed confirmation dialog proves delivery.
- Preserve an unchanged retry with one `submission_id`, and restore draft choices after an explanation request.
- Use no MCP server, localhost service, tunnel, external request, or database. Answers and form state are not persisted; only the user-controlled activation preference is stored locally.
- Fall back to a normal text reply when the host surface is unavailable.

## Non-goals for V0

- A general survey or form-building platform
- Conditional pages and complex branching
- External data, accounts, permissions, or shared state
- Automatic project changes based only on a board submission
- Codex CLI, VS Code, Apps SDK, or MCP compatibility claims

## Development gates

1. Keep the resolved owner choices in [`docs/OPEN_DECISIONS.md`](docs/OPEN_DECISIONS.md) as the decision record.
2. Validate schema, rendering, activation settings, accessibility, and duplicate-submit behavior.
3. Recheck the cancellation, retry, explanation summary, and restored-draft path in an explicitly authorized Codex Desktop run.
4. Verify a clean installation from the repository before packaging or publishing.

See [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) for the current product and test boundary.

The current static and browser checks are recorded in [`docs/TESTING.md`](docs/TESTING.md). A simple Korean input example is available at [`examples/basic-ko.json`](examples/basic-ko.json).

## License

[MIT](LICENSE)
