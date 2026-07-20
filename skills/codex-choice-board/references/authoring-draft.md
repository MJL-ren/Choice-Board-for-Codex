# Internal Board Draft

Use Draft only for a fresh fixed guided board with at least four questions, bundled `en` or `ko` copy, and no branching, custom `ui_copy`, restored state, completion state, supplied `flow_digest`, or other unsupported field. The deterministic compiler must create canonical schema-version-2 JSON before rendering.

Draft is not a public schema, renderer input, callback format, or saved state. Use [schema.md](schema.md) directly for every ineligible case.

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
      "allow_answer_note": true,
      "options": [["apply", "Apply it here"], ["handoff", "Hand it off"]]
    },
    {
      "id": "checks",
      "type": "multi",
      "label": "What should we check?",
      "options": [["scope", "Scope"], ["evidence", "Evidence"]]
    },
    {
      "id": "timing",
      "type": "single",
      "label": "When should it happen?",
      "options": [["now", "Now"], ["later", "Later"]]
    },
    {"id": "note", "type": "text", "label": "Anything else?"}
  ]
}
```

Top level requires `draft_version`, `mode`, `form_id`, `locale`, and `questions`; it may add `allow_explanation`, `allow_deferred_explanation`, and `submit_label`. Every question requires `id`, `type`, and `label`. Add only type-valid `description`, `required`, `allow_skip`, `placeholder`, `allow_other`, `allow_answer_note`, or `options`.

Omit defaults: `required: false`, `allow_skip: true`, `allow_other: true`, explanation enabled, and deferred explanation enabled. Choice options are ordered `[value, label]` pairs. Text questions have no options, Other, or answer note. Answer notes are choice-only and default to `false`; enable them explicitly when useful.

Compile once to a unique path:

```text
python scripts/compile_board_draft.py --draft <draft.json> --spec-output <canonical.json>
```

Render only the successful canonical output. Never reuse an older output after a failed compile.
