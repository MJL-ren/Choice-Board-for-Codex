# Choice Board for Codex

> Unofficial community project. Not affiliated with or endorsed by OpenAI.

Choice Board turns several related questions into one lightweight interactive
board inside Codex Desktop. It supports single choice, multiple choice, free
text, answer notes, explanations, review, and bounded one-layer branching. The
result returns to the same conversation as a readable summary plus a validated
machine payload.

No MCP server, localhost service, tunnel, database, or separate web app is
required.

## Why it exists

Long numbered questionnaires are easy to skip or answer ambiguously. Choice
Board gives each answer a clear shape while keeping the conversation as the
source of context. People see normal labels and controls; Codex receives a
canonical payload that it can validate before acting on the result.

## Interaction modes

| Mode | Best for | Behavior |
| --- | --- | --- |
| Compact | 1–3 fixed questions | Shows the questions together and submits once. |
| Guided | 4 or more fixed questions | Shows one question at a time with Back, Skip, explanation, notes, and final review. |
| Bounded branching | Prewritten follow-ups that genuinely depend on one earlier choice | Uses one layer of `show_if` conditions, clears hidden state, and returns the exact active path. |

Guided and bounded-branching boards do not have an arbitrary question-count
ceiling. The renderer still enforces per-field and fragment-size safety limits.
Nested predicates and model-generated follow-up branches are deliberately out
of scope.

## Requirements and support

- ChatGPT desktop app with Codex
- OpenAI's **Visualize** plugin installed and enabled
- Python 3.10 or newer available to Codex

| Surface | Status |
| --- | --- |
| Codex Desktop on Windows | Live tested |
| Codex Desktop on macOS | Intended, not independently verified yet |
| Mobile | Interactive board unavailable; plain-text fallback only |
| Codex CLI and IDE extension | Not currently claimed |

Plugin availability can vary by plan, workspace settings, role, surface, or
region. When Visualize is unavailable—or when a phone shows the raw inline
visualization directive—the skill immediately falls back to equivalent numbered
text questions in the same conversation.

## Installation

1. In the ChatGPT desktop app, open **Plugins**, find **Visualize** by OpenAI,
   and install or enable it.
2. Ask Codex to install the skill from this repository:

   ```text
   $skill-installer Install the skill from https://github.com/MJL-ren/Choice-Board-for-Codex/tree/main/skills/codex-choice-board
   ```

3. Start a new Codex task. If the skill or Visualize does not appear, restart
   the desktop app and confirm both are enabled.

OpenAI documents direct skill installation as a local authoring and
experimentation path. A packaged Codex plugin is the preferred route for wider
reusable distribution; this repository currently publishes the direct skill
folder while that packaging path is evaluated.

## Try it

The guaranteed invocation form is:

```text
$codex-choice-board Ask me 6 questions to narrow down a weekend activity. Let me choose more than one preference, add a note to an answer, and ask for an explanation before deciding.
```

Direct requests such as “give me choices” or “show this in a choice board” are
also recognized. The default remains fail-closed: the skill does not suggest or
open a board for unrelated requests unless the user explicitly changes the
activation mode to `suggest` or `auto`.

Ready-to-render examples are available in:

- [`examples/basic-en.json`](examples/basic-en.json)
- [`examples/basic-ko.json`](examples/basic-ko.json)
- [`examples/guided-ko.json`](examples/guided-ko.json)
- [`examples/branching-ko.json`](examples/branching-ko.json)

## How it works

1. Codex converts the questions into the canonical Choice Board schema.
2. A deterministic Python renderer validates the schema and injects it into a
   fixed, root-scoped HTML fragment.
3. Visualize displays native controls using the host theme.
4. The board calls `window.openai.sendFollowUpMessage(...)` to request one
   follow-up in the current conversation.
5. The receiving Codex task validates the marker, form identity, answer types,
   option values, flow digest, active path, and duplicate-submission identity
   before using the response.

A fulfilled host call is not treated as proof that the message reached the
conversation. The board keeps the draft available and offers an explicit,
byte-identical retry with the same `submission_id`. Automatic retry is never
used.

## Data and safety boundary

- Submitted answers appear in the current Codex conversation.
- The skill does not send answers to a separate server or database.
- Temporary JSON and HTML may be created in the task's local visualization
  directory; generated boards and user responses do not belong in this repo.
- Only the user-controlled activation preference is stored locally by the
  skill.
- Do not use the board to collect secrets, credentials, sensitive personal
  data, or final approval for destructive or external actions.
- Human-readable labels are presentation. The compact JSON envelope is the
  authority, and disagreement fails closed.

See [`SECURITY.md`](SECURITY.md) for reporting and trust-boundary details.

## Validation status

The current public candidate has deterministic schema, escaping, compiler,
branch-state, retry, and receiver-parity tests. Browser checks cover compact,
guided, answer-note, branching, locale fallback, 30-question guided flow, 320px
and 736px layouts, and host light/dark themes. Real Windows Codex Desktop runs
have also exercised submission, cancellation recovery, Back preservation,
immediate and deferred explanation, answer notes, and one bounded branch.

These checks do not claim screen-reader certification, automatic mobile-device
detection, or support on untested Codex surfaces. The exact boundary is recorded
in [`docs/TESTING.md`](docs/TESTING.md).

## Development

Install the browser-test dependency:

```powershell
npm install
npx playwright install chromium
```

Run the Python suite:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Validate the skill package:

```powershell
python -X utf8 path/to/skill-creator/scripts/quick_validate.py skills/codex-choice-board
```

Replace `path/to/skill-creator` with the validator location in your Codex
installation.
Browser commands and generated-fixture steps are documented in
[`docs/TESTING.md`](docs/TESTING.md).

Run every browser regression after installing Playwright:

```powershell
npm run test:browser
```

## Built with Codex

Development began on July 16, 2026, during the OpenAI Build Week submission
period. Codex and GPT-5.6 were used to turn repeated live UX failures into the
delivery-recovery contract, design the canonical schema and bounded branching
rules, implement the renderer and compiler, generate adversarial fixtures, and
run independent authoring comparisons. Product boundaries—especially the
desktop-only interactive surface, fail-closed activation, no-server design,
answer-note behavior, and one-layer branch limit—were explicit owner decisions.

The dated development and possible hackathon evidence boundary is recorded in
[`docs/DEVELOPMENT_PROVENANCE.md`](docs/DEVELOPMENT_PROVENANCE.md).

## Documentation

- [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) — product and runtime contract
- [`docs/OPEN_DECISIONS.md`](docs/OPEN_DECISIONS.md) — resolved design decisions
- [`docs/TESTING.md`](docs/TESTING.md) — current validation evidence and limits
- [`skills/codex-choice-board/references/schema.md`](skills/codex-choice-board/references/schema.md) — canonical input and callback schema

Contributions are welcome; read [`CONTRIBUTING.md`](CONTRIBUTING.md) before
opening a change.

## License

[MIT](LICENSE)
