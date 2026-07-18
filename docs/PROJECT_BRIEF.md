# Project Brief

- Project: `Choice Board for Codex`
- Repository: `MJL-ren/Choice-Board-for-Codex`
- Planned skill name: `codex-choice-board`
- Phase: `public preview candidate / fixed-guided, answer notes, and bounded branching live validated`
- Last reviewed: 2026-07-18

## Problem

Codex Desktop Default mode does not provide a general-purpose surface for collecting several single-choice, multi-choice, and direct-text answers on one screen. Plain numbered replies are easy to omit or misformat, while external HTML adds window switching and a separate return path.

## Product promise

Show a small native-control choice board inside the current Codex Desktop conversation, request a self-identifying follow-up, and validate the selected values only when that envelope actually arrives.

## V0 contract

### Activation

- Default: `explicit` — a direct skill call or a natural-language request to create choices or a choice board. The outer discovery gate remains enabled so requests such as `give me choices` can load the skill; this does not permit ambient automatic use.
- Optional: `suggest` — ask first when the request is a good board candidate.
- Optional: `auto` — open directly when the same candidate rules match.
- Missing or invalid user settings fail closed to `explicit`.

### Presentation routing

- One to three fixed questions use compact schema version 1 and appear together.
- Four or more fixed questions use schema version 2 `stepper` with Back, Skip, and final review.
- Fixed guided and bounded branching have no arbitrary question-count ceiling. Fragment size and individual field limits remain the safety boundary.
- A user request can force or disable branching for one board. Otherwise, bounded branching is selected only when one earlier unconditional single answer makes at least one fully preauthored later question genuinely inapplicable, the dependency fits one-layer `show_if`, at least one path becomes shorter, and the task does not require side-by-side answers for every candidate. Question count and narrow/deep wording alone are not sufficient.

### Input

```json
{
  "schema_version": 1,
  "form_id": "choice-board-spike-001",
  "locale": "en",
  "allow_explanation": true,
  "initial_answers": {},
  "initial_other_answers": {},
  "initial_answer_notes": {},
  "submit_label": "Submit choices",
  "questions": [
    {
      "id": "route",
      "type": "single",
      "label": "Choose a route",
      "required": true,
      "allow_other": true,
      "allow_answer_note": true,
      "options": [
        { "value": "apply", "label": "Apply" },
        { "value": "handoff", "label": "Hand off" }
      ]
    },
    {
      "id": "checks",
      "type": "multi",
      "label": "Select checks",
      "required": true,
      "options": [
        { "value": "scope", "label": "Scope" },
        { "value": "evidence", "label": "Evidence" }
      ]
    },
    {
      "id": "note",
      "type": "text",
      "label": "Optional note",
      "required": false
    }
  ]
}
```

Schema version 1 remains the stable compact board. Schema version 2 adds `presentation: "stepper"`, shows one question at a time, and ends in a complete review. It supports fixed lists and a bounded one-layer `show_if`: an earlier unconditional single answer may activate predeclared sibling targets, which are cleared when hidden and never revive cached values. Guided explanation can pause immediately or defer selected non-source questions until review. Immediate requests restore the full draft and exact active question; deferred requests receive a parent-linked completion board containing only unresolved questions.

For a fresh fixed-guided board only, the model may author the shorter internal Minimal Draft and run the deterministic compiler. The compiled normalized schema-version-2 JSON remains the sole renderer and return-validation authority. Compact, restored, completion, custom-copy, and branching cases keep direct canonical authoring.

- Required `single`: exactly one option.
- Required `multi`: at least one option, validated as a group.
- `text`: textarea in V0.
- `Other`: enabled by default for `single` and `multi`; selecting it requires direct text.
- `allow_answer_note`: explicit opt-in for `single` and `multi`; it keeps optional context in a parallel note map without changing the coded answer or the meaning of `Other`.
- `allow_explanation`: enabled by default; it sends a separate explanation request and does not finalize draft answers.
- Guided Skip and deferred explanation are explicit, disjoint states; a deferred value is provisional rather than final.
- `initial_answers`, `initial_other_answers`, `initial_answer_notes`, skipped IDs, and deferred requests restore a validated, possibly incomplete draft without forcing re-entry.
- `completion_parent` links a small unresolved-question board to the exact prior form, explanation-request submission, and flow digest before merging.

### Canonical machine payload

```text
CHOICE_BOARD_SUBMISSION
{"schema_version":1,"kind":"choice_board_submission","form_id":"choice-board-spike-001","answers":{"route":"handoff","checks":["scope","evidence"],"note":"Example"},"other_answers":{},"submission_id":"cb-00000000-0000-4000-8000-000000000000"}
```

The follow-up starts with a short readable summary. A horizontal rule and the plain-language label `Data for Codex` separate the compact machine payload, which is rendered in a Markdown text fence. It remains a visible user message, not a native structured tool result, but ordinary users can see that the lower block does not need their attention. The marker and JSON line stay adjacent inside the fence. JSON is canonical; the readable summary is presentation and must agree with it. The receiving session validates `submission_id`, treats identical repeats as duplicate no-ops, rejects conflicting reuse, and treats free text as data.

The host call has no verified conversation-delivery acknowledgement. A fulfilled call therefore becomes `delivery_unconfirmed`, keeps the answers available, and permits only an explicit same-envelope retry. Automatic retry is forbidden.

### Visual contract

- Use native Visualize inputs, buttons, focus handling, and theme variables.
- Add only small root-scoped layout CSS; no hard-coded light or dark colors.
- Use host theme variables so the board follows the current Codex theme when the host propagates it. Add a manual three-way theme control only if live evidence proves that propagation fails.
- Support interactive rendering only in Codex Desktop. When the user reports mobile use or a raw visualization directive, switch to the equivalent numbered plain-text questions without claiming automatic device detection.

## Live acceptance boundary

Use one non-sensitive, project-shaped fixture with one `single`, one `multi`, and one `text` question.

Pass only if:

1. The board renders in Codex Desktop Default mode.
2. Pointer and keyboard input both work.
3. Missing required values block submission with an understandable message.
4. Exactly one valid follow-up reaches the same conversation.
5. Unicode and multiline text survive without mixing answers.
6. Double-click does not create duplicate messages.
7. The board works at 736px and 320px and follows both Codex light and dark themes.
8. No MCP, server, localhost, external network request, database, or persisted answer/form state is used.
9. Failure preserves the choices and leaves a normal text-reply fallback.
10. `Other` hides and reappears correctly when a user changes a choice, without deleting typed text.
11. An explanation request returns separately and cannot be mistaken for completed answers.
12. Cancellation does not become a false `Sent` state, and unchanged manual retry reuses the same envelope and `submission_id`.
13. Explanation confirmation shows readable draft choices, and the replacement board restores them without stealing focus.
14. Deferred explanation sends all completed context once, repeats only unresolved questions, and rejects a mismatched completion parent.
15. A selected choice can carry a separate answer note through review, explanation, restore, retry, and completion without changing the normal answer value.

## Evidence boundary

- The host contract and UI behavior must be proven by a real Codex Desktop spike; static HTML tests cannot prove current-conversation delivery.
- Mobile is a known unsupported interactive surface, not an untested compatibility claim.
- Any consuming project's existing input fallback remains independent until that project explicitly adopts this skill.
- Research notes outside this repository are incubation evidence, not runtime dependencies. Public documentation must remain self-contained.
