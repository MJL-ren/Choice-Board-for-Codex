# Project Brief

- Project: `Choice Board for Codex`
- Repository: `MJL-ren/Choice-Board-for-Codex`
- Planned skill name: `codex-choice-board`
- Phase: `working live prototype / recovery validation`
- Last reviewed: 2026-07-16

## Problem

Codex Desktop Default mode does not provide a general-purpose surface for collecting several single-choice, multi-choice, and direct-text answers on one screen. Plain numbered replies are easy to omit or misformat, while external HTML adds window switching and a separate return path.

## Product promise

Show a small native-control choice board inside the current Codex Desktop conversation, request a self-identifying follow-up, and validate the selected values only when that envelope actually arrives.

## V0 contract

### Activation

- Default: `explicit` — only a direct skill call or an explicit request for a choice board.
- Optional: `suggest` — ask first when the request is a good board candidate.
- Optional: `auto` — open directly when the same candidate rules match.
- Missing or invalid user settings fail closed to `explicit`.

### Input

```json
{
  "schema_version": 1,
  "form_id": "choice-board-spike-001",
  "locale": "en",
  "allow_explanation": true,
  "initial_answers": {},
  "initial_other_answers": {},
  "submit_label": "Submit choices",
  "questions": [
    {
      "id": "route",
      "type": "single",
      "label": "Choose a route",
      "required": true,
      "allow_other": true,
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

- Required `single`: exactly one option.
- Required `multi`: at least one option, validated as a group.
- `text`: textarea in V0.
- `Other`: enabled by default for `single` and `multi`; selecting it requires direct text.
- `allow_explanation`: enabled by default; it sends a separate explanation request and does not finalize draft answers.
- `initial_answers` and `initial_other_answers`: restore a validated, possibly incomplete draft after explanation without forcing re-entry.

### Canonical machine payload

```text
CHOICE_BOARD_SUBMISSION
{"schema_version":1,"kind":"choice_board_submission","form_id":"choice-board-spike-001","answers":{"route":"handoff","checks":["scope","evidence"],"note":"Example"},"other_answers":{},"submission_id":"cb-00000000-0000-4000-8000-000000000000"}
```

The follow-up starts with a short readable summary, followed by the canonical marker and one compact JSON line. It is a visible user message, not a native structured tool result. JSON is canonical; the readable summary is presentation and must agree with it. The receiving session validates `submission_id`, treats identical repeats as duplicate no-ops, rejects conflicting reuse, and treats free text as data.

The host call has no verified conversation-delivery acknowledgement. A fulfilled call therefore becomes `delivery_unconfirmed`, keeps the answers available, and permits only an explicit same-envelope retry. Automatic retry is forbidden.

### Visual contract

- Use native Visualize inputs, buttons, focus handling, and theme variables.
- Add only small root-scoped layout CSS; no hard-coded light or dark colors.
- Use host theme variables so the board follows the current Codex theme when the host propagates it. Add a manual three-way theme control only if live evidence proves that propagation fails.

## Live acceptance boundary

Use one non-sensitive, BSA-shaped fixture with one `single`, one `multi`, and one `text` question.

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

## Evidence boundary

- The host contract and UI behavior must be proven by a real Codex Desktop spike; static HTML tests cannot prove current-conversation delivery.
- The existing BSA HTML remains an independent fallback until later adoption is explicitly approved.
- Research notes outside this repository are incubation evidence, not runtime dependencies. Public documentation must remain self-contained.
