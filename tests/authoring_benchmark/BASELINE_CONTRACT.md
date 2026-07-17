# Baseline contract — current public spec

Convert the locked fixture into the existing Choice Board renderer input JSON.
Do not improve, shorten, translate, reorder, or reinterpret fixture content.

## Required shape

Top level:

```json
{
  "schema_version": 2,
  "presentation": "stepper",
  "form_id": "...",
  "locale": "ko",
  "questions": []
}
```

Question fields use the current public schema:

- Every question: `id`, `type`, `label`.
- Add `description` only when the fixture has one.
- Add `required: true` only when required. Omit the default `false`.
- Omit `allow_skip` when true. Guided questions default to true.
- Text: add `placeholder` only when the fixture has one.
- Choice: `options` is an ordered array of objects shaped as
  `{ "value": "...", "label": "..." }`.
- Choice: add `allow_other: false` only when the fixture disables Other. Omit
  the default `true`.

Do not add initial answer state, `flow_digest`, branching fields, comments, or
Markdown fences. The output file must contain one JSON object only.

The harness uses a strict loader and rejects duplicate keys, unknown fields,
content drift, missing values, and reordered questions or options.
