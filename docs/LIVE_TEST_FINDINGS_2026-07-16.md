# Codex Desktop Live Test Findings — 2026-07-16

## Scope

This note records live Codex Desktop behavior and follow-up improvements for the working `codex-choice-board` prototype. It does not change the public contract or authorize implementation by itself.

## Confirmed in the first live sequence

The food-preference exercise completed three consecutive boards with five questions each.

- Three distinct `form_id` values returned to the same conversation in order.
- `single`, required `multi`, optional `multi`, and `text` answers returned successfully.
- Korean text, punctuation, and informal text survived the follow-up message.
- Multi-select option values and display order matched the visible summary.
- The human-readable summary and canonical JSON agreed in all three submissions.
- No MCP, external server, localhost process, or persistent answer store was used.

## Return-envelope decision

Keep both layers, but assign one authority to each.

- The `선택 보드 답변` section is a human-readable presentation summary.
- The final complete `CHOICE_BOARD_SUBMISSION` or `CHOICE_BOARD_EXPLANATION_REQUEST` line and immediately following JSON line are the canonical machine payload.
- If the summary and canonical payload disagree, fail closed and report the mismatch. Do not silently choose one answer set.
- Keep `kind` inside the JSON even though the marker identifies the message type; the two values provide a cheap consistency check.

## Improvement candidates

### P0 — Do not equate a fulfilled host call with delivered conversation input

The first explanation-request edge test produced a real delivery ambiguity:

- The user rapidly activated `설명 요청하기` twice.
- A confirmation dialog that had appeared on earlier single-click submissions did not remain visible.
- The board changed to `보냈어요` and permanently disabled its controls.
- The current Codex thread contained no `CHOICE_BOARD_EXPLANATION_REQUEST` callback afterward; only the user's manual incident report appeared.

The retry reproduced the same state with a clearer cause:

- A single explanation activation opened the host confirmation dialog.
- The user explicitly chose `Cancel`.
- `sendFollowUpMessage(...)` still fulfilled rather than throwing in the fragment's observed control flow.
- The board immediately changed to `보냈어요`, disabled every answer, and offered no retry.
- No canonical explanation callback appeared in the conversation.

Treat this as `delivery unconfirmed / retry unavailable`, not a successful duplicate-suppression result. The fulfilled `sendFollowUpMessage` awaitable proves only that the host call returned; it did not prove that a canonical message became a conversation turn in this observation.

Before public release, consider:

- wording the immediate board state as `전송 요청됨` rather than confirmed delivery;
- preserving the disabled answers visibly instead of implying that the conversation received them;
- assigning a stable `submission_id` before the first send;
- allowing an explicit retry with the same `submission_id` after an unconfirmed result;
- requiring the receiver to deduplicate identical `submission_id` values;
- providing a plain-text fallback when the callback does not appear.

Do not add a blind automatic retry. The fragment cannot observe the conversation and could create a duplicate after a delayed successful delivery.

The current implementation also ignores the resolved value entirely. Inspect any returned `isError` or future documented result before deciding success, but do not assume that a fulfilled value provides delivery acknowledgement. If approval and cancellation remain indistinguishable, keep the state explicitly unconfirmed and pair manual retry with a stable `submission_id` and receiver-side deduplication.

### P0 — Show selected drafts in the explanation confirmation summary

The retry confirmed that the host confirmation view did not visibly show the already selected choice labels. It showed the free-text explanation context, causing the user to reasonably believe that button selections would be omitted.

The renderer did collect the choices in `draft_answers` and `draft_other_answers`, and the canonical JSON was included in the raw prompt. The usability defect is in the human-readable explanation summary: it currently contains only the explanation request text, while normal submissions use `readableSummary(...)`.

Before the next live explanation test, include a concise `현재 선택 초안` block built from the same collected values and labels. The confirmation surface must let a non-developer verify both the explanation question and the choices that will accompany it without reading JSON.

### P0 — Clarify canonical authority

Add the return-envelope authority and mismatch rule to `SKILL.md` and the schema reference before public release.

### P1 — Add optional sequential-flow identity

Consider optional fields for multi-board workflows:

- `flow_id`
- `step`
- `parent_form_id`

They should detect stale, out-of-order, or cross-flow submissions without burdening one-shot boards.

### P1 — Add bounded multi-select counts

Consider optional `min_selected` and `max_selected` fields. `required` currently expresses only at least one selection and cannot represent “choose exactly two” or “choose up to three.”

### P1 — Restore drafts after an explanation request

The explanation callback returns `draft_answers` and `draft_other_answers`, but a replacement board cannot currently prefill them. Consider `initial_answers` and `initial_other_answers` so asking for clarification does not force the user to repeat prior selections.

### P1 — Make an optional single choice reversible

The first edge run also exposed the native radio-control behavior: after selecting one single-choice option, the user could switch to another option but could not return the question to an unanswered state. For a required question this is consistent with the answer contract, but it makes test recovery less obvious; for an optional single-choice question it would prevent the user from withdrawing an accidental answer.

Keep required-answer semantics unchanged. Before public release, decide whether optional single-choice questions need a small `선택 지우기` action or an explicit `응답하지 않음` option. Do not add a board-wide reset merely to support this test case.

### P2 — Make render verification one operation

Consider a renderer report mode that returns `form_id`, question count, labels, byte size, fragment-only status, external-request status, and follow-up-function presence as one JSON result.

### Deferred — Do not add new question types yet

Do not add ranking, drag-and-drop, branching pages, or a general survey builder until the current three question types and recovery paths are stable. A bounded multi-select plus a later single-choice question covers most prioritization needs.

## Live paths still requiring evidence

The local browser smoke test covers these, but the first Codex Desktop sequence did not exercise them directly:

- selected `Other` plus required direct text;
- required-answer blocking and focus movement;
- explanation-request callback with incomplete or draft answers;
- a replacement board after explanation and whether drafts are restored;
- rapid duplicate activation producing only one follow-up;
- installed activation modes and metadata reload behavior;
- failed follow-up send and retry.

The failed-send path is deliberately deferred because reliably injecting a host send failure is not part of the current live-test surface.

The rapid duplicate test unexpectedly exposed a host-return-without-observed-callback path, so duplicate suppression remains unproven in the live app even though the local browser test passes.

## Implementation response

The repository implementation was tightened after the two failed edge runs:

- fulfilled host calls now end in an explicit `delivery_unconfirmed` state instead of `보냈어요`;
- thrown errors and `{ isError: true }` remain retryable without losing answers;
- unchanged manual retries reuse the exact prompt and stable `submission_id`, while edits create a new envelope;
- explanation confirmations now include a readable `현재 선택 초안` section;
- schema-v1 `initial_answers` and `initial_other_answers` restore a validated incomplete draft;
- the receiving skill contract now treats canonical JSON as authority and handles duplicate/conflicting submission IDs fail-closed;
- required error and delivery status text no longer use the smallest text style.

The Python suite and headless Chrome smoke test pass these paths locally. Codex Desktop cancellation, retry, callback delivery, and draft restoration remain `PENDING LIVE REVALIDATION` until a new authorized board run completes.

Sequential flow identity, bounded multi-select counts, optional single-choice clearing, and renderer report mode remain deferred candidates. They were not required to close the observed delivery and explanation failures.

## Edge-test observation log

### Produce preference edge run 1

- Intended form: `produce-preference-edge-r1`
- Observed event: rapid double activation of the explanation action
- Board state afterward: `보냈어요`, controls disabled
- Host confirmation UI: not visibly available after the rapid activation
- Canonical callback in current thread: absent, verified through the thread history
- Verdict: `FAIL — delivery unconfirmed and no retry path`
- Draft answers: unavailable to the receiving model because no canonical callback arrived
- Clarified interaction: question 4 received a radio selection and could not be returned to an unanswered state; the user instead left required multi-choice question 3 blank.
- Required-field blocking/focus: `INCONCLUSIVE`. It is unknown whether a normal submission was attempted before explanation mode, and explanation requests are allowed to carry incomplete drafts.
- Final `Other` submission and explanation-resume behavior: not yet dispositioned from this run

### Produce preference edge retry 1

- Intended form: `produce-preference-edge-r1-retry`
- Required multi-choice question 3 was left blank for a normal submission attempt.
- Required-answer blocking: `PASS`; a visible message named question 3 and asked the user to select an item.
- Focus or scroll movement to question 3: `NOT OBSERVED`; the user reported no screen movement.
- Explanation activation: one click opened the host confirmation dialog.
- Confirmation preview: selected choice labels were not visibly represented; free-text content was visible.
- User action in confirmation dialog: `Cancel`.
- Board state afterward: `보냈어요`, all controls disabled, no retry.
- Canonical callback in current thread: absent.
- Verdict: `FAIL — cancellation treated as delivery, draft-choice preview inadequate, retry unavailable`.
- Canonical `Other` and explanation-draft payload delivery remain unverified because cancellation produced no conversation message.

## Next live test protocol

Pause further explanation-request live tests until the confirmation summary and cancellation-safe state handling are changed. Repeating the same flow would force the user to re-enter answers while the receiver still lacks a delivery oracle.

After the narrow fix, use one small fruit-and-vegetable preference board.

1. Select `Other` for one required choice and enter direct text.
2. Leave the designated required multi-choice question blank, keep explanation mode off, and attempt a normal submission; verify blocking and focus.
3. Record the visible blocking/focus behavior in the board's test-note field.
4. Complete the multi-choice question, enable explanation mode, and submit an explanation request with drafts using one activation only.
5. Explain the requested distinction and issue a replacement board.
6. Observe whether the previous drafts are restored, then complete one canonical final submission.

Do not repeat the rapid double-activation test until the unconfirmed-delivery recovery design is implemented. The first run already produced a meaningful failure and repeating it would risk losing another draft without adding a reliable oracle.

Record the patched live result before calling the recovery path release-ready.
