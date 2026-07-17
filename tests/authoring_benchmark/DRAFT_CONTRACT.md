# Draft contract — minimal Board Draft JSON

Convert the locked fixture into the internal Draft JSON below. Do not
improve, shorten, translate, reorder, or reinterpret fixture content. This is
authoring input only; the deterministic compiler creates the public spec. The
shipped adapter uses this shape only for fresh fixed-guided boards.

## Required shape

Top level:

```json
{
  "draft_version": 1,
  "mode": "guided",
  "form_id": "...",
  "locale": "ko",
  "questions": []
}
```

Question fields keep the familiar names:

- Every question: `id`, `type`, `label`.
- Add `description` only when the fixture has one.
- Add `required: true` only when required. Omit the default `false`.
- Omit `allow_skip` when true. Guided questions default to true.
- Text: add `placeholder` only when the fixture has one.
- Choice: `options` is an ordered array of two-item pairs:
  `["value", "label"]`.
- Choice: add `allow_other: false` only when the fixture disables Other. Omit
  the default `true`.

Do not add public `schema_version` or `presentation`, initial answer state,
`flow_digest`, branching fields, comments, or Markdown fences. The output file
must contain one JSON object only.

The compiler and harness reject duplicate keys, unknown fields, malformed
option pairs, content drift, missing values, and reordered questions or options.
