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

- The answer-summary section is a human-readable presentation layer.
- The final complete `CHOICE_BOARD_SUBMISSION` or `CHOICE_BOARD_EXPLANATION_REQUEST` line and immediately following JSON line are the canonical machine payload.
- If the summary and canonical payload disagree, fail closed and report the mismatch. Do not silently choose one answer set.
- Keep `kind` inside the JSON even though the marker identifies the message type; the two values provide a cheap consistency check.

## Improvement candidates

### P0 — Do not equate a fulfilled host call with delivered conversation input

The first explanation-request edge test produced a real delivery ambiguity:

- The user rapidly activated the explanation-request action twice.
- A confirmation dialog that had appeared on earlier single-click submissions did not remain visible.
- The board changed to a localized sent-confirmation state and permanently disabled its controls.
- The current Codex thread contained no `CHOICE_BOARD_EXPLANATION_REQUEST` callback afterward; only the user's manual incident report appeared.

The retry reproduced the same state with a clearer cause:

- A single explanation activation opened the host confirmation dialog.
- The user explicitly chose `Cancel`.
- `sendFollowUpMessage(...)` still fulfilled rather than throwing in the fragment's observed control flow.
- The board immediately changed to a sent-confirmation state, disabled every answer, and offered no retry.
- No canonical explanation callback appeared in the conversation.

Treat this as `delivery unconfirmed / retry unavailable`, not a successful duplicate-suppression result. The fulfilled `sendFollowUpMessage` awaitable proves only that the host call returned; it did not prove that a canonical message became a conversation turn in this observation.

Before public release, consider:

- wording the immediate board state as delivery requested rather than confirmed delivery;
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

Before the next live explanation test, include a concise current-draft block built from the same collected values and labels. The confirmation surface must let a non-developer verify both the explanation question and the choices that will accompany it without reading JSON.

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

Keep required-answer semantics unchanged. Before public release, decide whether optional single-choice questions need a small clear-selection action or an explicit no-response option. Do not add a board-wide reset merely to support this test case.

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

- fulfilled host calls now end in an explicit `delivery_unconfirmed` state instead of a sent-confirmation state;
- thrown errors and `{ isError: true }` remain retryable without losing answers;
- unchanged manual retries reuse the exact prompt and stable `submission_id`, while edits create a new envelope;
- explanation confirmations now include a readable current-draft section;
- schema-v1 `initial_answers` and `initial_other_answers` restore a validated incomplete draft;
- the receiving skill contract now treats canonical JSON as authority and handles duplicate/conflicting submission IDs fail-closed;
- required error and delivery status text no longer use the smallest text style.

The Python suite and headless Chrome smoke test pass these paths locally. A later authorized Codex Desktop run also completed the cancellation, retry, callback delivery, readable draft, replacement-board restoration, and final submission path.

Sequential flow identity, bounded multi-select counts, optional single-choice clearing, and renderer report mode remain deferred candidates. They were not required to close the observed delivery and explanation failures.

## Edge-test observation log

### Produce preference edge run 1

- Intended form: `produce-preference-edge-r1`
- Observed event: rapid double activation of the explanation action
- Board state afterward: sent-confirmation state, controls disabled
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
- Board state afterward: sent-confirmation state, all controls disabled, no retry.
- Canonical callback in current thread: absent.
- Verdict: `FAIL — cancellation treated as delivery, draft-choice preview inadequate, retry unavailable`.
- Canonical `Other` and explanation-draft payload delivery remain unverified because cancellation produced no conversation message.

## Patched live recheck

- Fixture: `fruit-vegetable-retry-test-v2`, five non-sensitive fruit and vegetable preference questions.
- The first host confirmation was cancelled. No callback appeared, and the board kept the visible draft while showing a retry-the-same-content action and an explicit delivery-unconfirmed explanation.
- The manual retry produced one canonical explanation request in the same conversation.
- Its readable current-draft summary contained the same radio and checkbox labels as the canonical draft payload.
- The replacement board restored all selected values and returned to an editable state.
- The final canonical submission matched the restored draft and used a distinct final-submission ID.
- Verdict: `PASS — patched cancellation, retry, explanation preview, draft restoration, and final submission path`.

The conversation cannot expose the cancelled attempt's hidden envelope, so the live run does not independently compare the cancelled and retried `submission_id`. Byte-identical retry identity remains covered by the browser test.

## Answer note — live validation, 2026-07-17

- Added an explicit choice-only `allow_answer_note` capability without changing the normal `answers` or `other_answers` shapes.
- Notes return through sparse `answer_notes` / `draft_answer_notes` maps and restore through `initial_answer_notes`. Old note-disabled boards omit these fields and retain their previous guided-flow digest.
- Python validation covers opt-in normalization, Minimal Draft preservation, note-enabled flow identity, restore without digest drift, and rejection on unknown, text, disabled, neutral, wrong-type, or overlong states.
- A dedicated headless Chrome run passed compact and guided selection, collapsed note entry, changing a valid choice, clearing the final multi selection, Skip clearing, Back preservation, review/summary parity, `Other` plus note separation, immediate explanation, restored notes without focus theft, exact retry, new submission identity after editing, and 320px light/dark layout.
- Existing compact and guided browser suites still pass and confirm that boards without the feature do not gain note fields in returned payloads.
- A real three-question guided callback returned the expected single and multi answers plus three separate answer notes. The readable Korean summary matched the canonical `answer_notes` map, and the live tester confirmed that every note survived repeated Back/Next navigation.
- Live feedback asked for slightly stronger at-a-glance hierarchy without adding cards or a custom color system. The question heading now uses the host's H3 size, the localized required marker uses the host's theme-aware validation color, the choice hint is underlined, and the collapsed note action uses normal-size medium-weight text.
- Status: `LIVE PASS — callback, readable summary, canonical note map, and Back/Next preservation verified; lightweight hierarchy polish implemented`.

## Mobile observation

- A phone mirrored the same desktop-backed task but rendered the raw `::codex-inline-vis` directive instead of the board.
- Visualize cannot be installed on that mobile surface.
- Verdict: `UNAVAILABLE — use the numbered plain-text fallback and do not emit another board after the user reports mobile use`.
- The mirrored task does not provide reliable automatic device detection.

## Fixed guided Phase A — local readiness, 2026-07-17

- Added a separate schema-version-2 `stepper` prototype without changing compact schema version 1.
- The renderer rejects branch fields, restores a known `initial_question_id`, and locks the normalized form definition with `flow_digest`.
- Python tests: 16 passed.
- Existing compact Chrome smoke: passed.
- New guided Chrome smoke: passed for one-visible-question navigation, no auto-advance, Back preservation, optional Skip clearing, full review, sequential correction, explanation identity, manual retry, restored position, host errors, and 320/736px light/dark layouts.
- First live submission: `guided-food-phase-a-live-001` returned to the same conversation with schema version 2, `presentation: stepper`, five correctly typed answer fields, an empty valid Other map, a new submission ID, and the exact renderer-computed flow digest.
- The readable Korean summary matched the canonical values and option labels in question order.
- The live tester then traversed backward through earlier questions and confirmed that every prior selection remained restored. Live Back preservation is therefore verified.
- Status: `BASIC LIVE SUBMISSION + BACK PRESERVATION PASS — final guided delivery and Back state are verified; live Skip behavior and explanation replacement to the same question remain only partially verified`.

### Follow-up message readability polish — 2026-07-17

- Kept the readable summary and canonical JSON transport unchanged in authority.
- Added a horizontal rule, a plain-language `Data for Codex` explanation, and a Markdown text fence around the adjacent marker-plus-JSON pair.
- This is presentation-only: the receiver still finds the exact marker line and parses the immediately following single JSON line.

### All-question explicit Skip contract — 2026-07-17

- Guided schema version 2 now enables Skip on every question by default, including required questions. A form may explicitly disable it per question when the workflow cannot proceed without that answer.
- An intentional skip is represented by ordered `skipped_question_ids` rather than being inferred from an empty answer. Explanation requests use `draft_skipped_question_ids`, and restored boards use `initial_skipped_question_ids`.
- Returning with Back and entering an answer removes that question from the skipped set. Skipping after an answer clears the answer and its Other text.
- Python tests: 17 passed. Compact and guided Chrome smoke tests passed, including required-question Skip, restoration, replacement after Back, readable review, explanation draft state, and final canonical state.
- Status: `SUPERSEDED — the combined run below verified Skip replacement and the immediate explanation callback`.

### Combined Skip replacement and immediate explanation run — 2026-07-17

- Fixture: `guided-final-skip-explanation-test-001`.
- A required text question was explicitly skipped, revisited through Back, and answered before the explanation request.
- The canonical callback contained the restored text answer and `draft_skipped_question_ids: []`, so the prior Skip state was removed instead of being confused with a blank answer.
- The callback returned at the selected fourth question with all earlier single, multi, and text drafts intact. A replacement board was rendered with the same form ID, flow digest, active question, and draft values.
- The user moved into deferred-explanation design before submitting the replacement board, so this run proves callback and replacement generation but not the replacement board's final submission.
- Status: `IMMEDIATE EXPLANATION CALLBACK PASS — resumed final submission not exercised in this run`.

### Deferred explanation — local implementation — 2026-07-17

- Guided explanation now offers immediate and defer-and-continue actions as distinct choices.
- Deferred questions retain an optional provisional answer, remain separate from Skip, restore their question-specific request after Back, and appear as decide-after-explanation in review.
- A review containing deferred questions sends `after_completion`, not a completed Choice Board submission. The follow-up completion board contains only the deferred questions and carries a validated parent form ID, submission ID, and flow digest.
- Python tests: 19 passed. Compact and guided Chrome smoke tests passed, including immediate-mode regression, unanswered required deferral, provisional-answer editing, parent-linked completion payload, duplicate suppression, retry identity, responsive layout, and theme checks.
- Status: `LOCAL PASS — followed by the complete live run below`.

### Deferred explanation through completion — Codex Desktop live run — 2026-07-17

- The six-question guided form `deferred-explanation-live-test-20260717-001` left required question `priority_rule` unanswered and marked it decide-after-explanation while preserving five completed answers.
- Review returned one canonical `after_completion` request. The deferred list contained only `priority_rule`; skipped and deferred state remained disjoint, and the flow digest matched the rendered form.
- The receiver used the completed answers as context, explained only the four pending option meanings, and rendered one compact completion question rather than recreating the six-question form.
- The completion submission selected `recovery_value` and repeated the exact parent form ID, explanation-request submission ID, and parent flow digest. The receiver accepted only that deferred question and merged it into the preserved draft.
- No completed question was re-asked or resubmitted, and the original task continued with all six final answers.
- Status: `LIVE PASS — fixed guided immediate and deferred explanation core is validated`.

## Internal authoring adapter — 2026-07-17

- Six counterbalanced benchmark pairs covered 5, 10, and 15 logical questions; all twelve fresh target tasks passed on their first authored input.
- Minimal Draft and direct public authoring produced byte-identical normalized canonical data and rendered output in every pair.
- Minimal Draft used about 15% fewer semantic input bytes and showed a modest local authoring-time signal. Individual-pair variance was large enough that this is not a speed guarantee; the public aggregate is recorded in [`../tests/authoring_benchmark/RESULTS.md`](../tests/authoring_benchmark/RESULTS.md).
- Decision: use Draft only inside the skill for a fresh fixed-guided board, compile to canonical JSON, and keep every public schema, renderer, callback, restore, and completion contract unchanged.
- The 15-question profile was a synthetic authoring benchmark split into 12+3 under the then-current production limit. On 2026-07-18 that arbitrary schema-version-2 count ceiling was removed; the historical benchmark result and split remain unchanged evidence.

## Bounded branching — first Codex Desktop callback, 2026-07-17

- Fixture: `branching-agenda-intake-ko-001`, with 12 declared questions, one unconditional source, eight conditional sibling targets across four routes, and three common follow-up questions.
- The user selected the `compare` route. Exactly its two route-specific questions plus the source and three common questions appeared in the returned readable summary: six active and six hidden questions.
- The canonical callback returned the exact ordered path `agenda_type, choice_basis, choice_shape, time_horizon, hard_constraints, output_shape` in `active_question_ids`.
- All six hidden targets remained present only as type-neutral values in `answers`. They were absent from Other, answer notes, Skip, deferred explanation, readable summary, and active-position state.
- The installed independent receiver helper recomputed the same path from the canonical spec and source answer. Schema version, form ID, presentation, option values, answer types, and flow digest all validated.
- The readable Korean labels matched the canonical option values. The callback had no notes, skipped questions, or Other answers.
- This run proves live route selection, active-only review/summary, exact active-path return, and current-conversation delivery. It does not independently prove live source-change clearing through Back; that remains covered by the dedicated browser regression.
- Status: `LIVE CALLBACK PASS — first bounded branching path validated; optimization Council pending explicit invocation`.
