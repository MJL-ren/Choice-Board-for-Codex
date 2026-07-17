# Internal Board Draft

Use this format only to author a **new fixed guided board** more concisely. It
is not a public schema, renderer input, callback format, or saved user state.
The deterministic compiler must turn it into the normalized schema-version-2
spec before the existing renderer sees it.

Do not use Draft for compact boards, explanation resume, completion boards,
custom `ui_copy`, branching, supplied `flow_digest`, or any `initial_*` state.
Write those directly in the canonical format from [schema.md](schema.md).

```json
{
  "draft_version": 1,
  "mode": "guided",
  "form_id": "guided-example-001",
  "locale": "en",
  "questions": [
    {
      "id": "route",
      "type": "single",
      "label": "Which route should we take?",
      "required": true,
      "allow_answer_note": true,
      "options": [
        ["apply", "Apply it here"],
        ["handoff", "Hand it off"]
      ]
    },
    {
      "id": "note",
      "type": "text",
      "label": "Anything else?"
    }
  ]
}
```

## Concise rules

- Top level: `draft_version`, `mode`, `form_id`, `locale`, `questions`, plus
  optional `allow_explanation`, `allow_deferred_explanation`, and
  `submit_label`.
- Every question: `id`, `type`, `label`.
- Add `description`, `required`, `allow_skip`, `placeholder`, `allow_other`,
  `allow_answer_note`, or `options` only when needed by that question type.
- Omit defaults: `required: false`, `allow_skip: true`, `allow_other: true`,
  board explanation enabled, and deferred explanation enabled.
- Choice options are ordered `[value, label]` pairs. Text questions have no
  options, `allow_other`, or `allow_answer_note`.
- `allow_answer_note` is choice-only and defaults to `false` for compatibility.
  When the current board should let a user keep a comment with a selected
  answer, set it to `true` explicitly. The compiler never adds it silently.
- Keep at least four questions. There is no fixed question-count ceiling and the compiler never splits a large form; the rendered fragment must still remain below the normal 2 MB safety boundary.

The compiler rejects duplicate keys, non-finite numbers, unknown fields,
malformed pairs, reserved or duplicate values, invalid IDs and types, and any
state or branch field outside this narrow contract.

Compile to a unique thread-temporary path:

```text
python scripts/compile_board_draft.py --draft <draft.json> --spec-output <canonical.json>
```

Render only after that exact command succeeds, using `<canonical.json>` with
`render_board.py`. Keep the canonical file as the authority for validating the
returned envelope. Never reuse an older canonical output after a failed
compile.
