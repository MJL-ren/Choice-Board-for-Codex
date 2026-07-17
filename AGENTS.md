# Choice Board for Codex — Repository Instructions

## Purpose

This repository develops an unofficial community skill that collects single,
multiple, and free-text answers in an inline Codex Desktop board and requests a
validated follow-up in the current conversation.

## Supported boundary

- Product name: `Choice Board for Codex`
- Skill name and folder: `codex-choice-board`
- Supported interactive host: Codex Desktop with the Visualize plugin
- Mobile behavior: plain-text fallback; never claim interactive rendering
- Question types: `single`, `multi`, and `text`
- Presentation: compact for 1–3 fixed questions, guided for longer fixed flows,
  and bounded one-layer branching only when a prewritten later question is
  genuinely inapplicable on at least one earlier-single route
- Transport: `window.openai.sendFollowUpMessage({ prompt, title })`
- Persistence: no answer database or server; only the user-controlled activation
  preference may be stored locally

Do not add MCP, localhost services, external requests, nested predicates,
model-generated branch questions, or a general survey-builder surface without a
separate design decision.

## Repository layout

```text
skills/codex-choice-board/  Installable skill
examples/                   Non-sensitive public examples
tests/                      Schema, rendering, browser, and return-contract tests
docs/                       Product decisions and validation records
```

Generated HTML, task-specific JSON, user answers, screenshots containing private
data, task IDs, and benchmark run directories must not be committed.

## Implementation rules

- Keep `SKILL.md` concise and put detailed contracts in `references/`.
- Treat canonical JSON as the runtime authority. Internal Board Draft input must
  compile into canonical JSON before rendering.
- Keep the static HTML fragment responsible for interaction and the Python
  renderer responsible for deterministic validation and safe data injection.
- Escape labels and free text before insertion into HTML or follow-up prompts.
- Validate markers, schema versions, form and question IDs, answer types, option
  values, flow identity, and active branch paths again after a callback arrives.
- Preserve the readable-summary / machine-payload separation. A mismatch fails
  closed.
- Do not treat a fulfilled host call as delivery confirmation. Keep explicit
  byte-identical retry and duplicate/conflict checks.
- Keep hidden branch state clear-only and recompute `active_question_ids` from
  canonical data.

## Validation

Run the relevant checks after changes:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -X utf8 path/to/skill-creator/scripts/quick_validate.py skills/codex-choice-board
```

Use the browser commands in `docs/TESTING.md` for UI or state changes. Distinguish
local static/browser checks from a real Codex Desktop callback. Never describe an
untested surface as supported.

## Change and release safety

- Preserve unrelated working-tree changes.
- Do not update a user's installed skill copy, open a live Visualize board,
  commit, push, tag, publish, or change repository visibility unless the owner
  explicitly requests that action.
- Keep credentials, personal data, private task transcripts, and local benchmark
  evidence out of Git.
- Before a public release, verify installation from a clean checkout and confirm
  that README claims match the actual supported surfaces.
