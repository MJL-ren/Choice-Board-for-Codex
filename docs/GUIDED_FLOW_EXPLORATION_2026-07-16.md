# Guided Flow Exploration — 2026-07-16

## Status

Phase A fixed-guided submission, Back, Skip replacement, immediate explanation, and deferred explanation through its small completion board were exercised in Codex Desktop on 2026-07-17. The stable schema-v1 compact board remains unchanged. Phase B bounded branching now passes canonical normalization, clear-only path state, receiver-parity, accessibility, and browser regressions; its first authorized Codex Desktop callback remains pending.

## Evidence from the live comparison

- Five ordinary questions plus explanation and recovery controls already create a long vertical board. Later questions and the submit action fall outside the first view.
- The compact board remains efficient when a person needs to scan or compare a few independent answers together.
- A step-based reference keeps attention on the current decision and supports Back, Next, Skip, and progress, but hides earlier context and needs a final review.
- The mobile mirror displayed the raw visualization directive. Changing the board layout cannot make the interactive surface available on mobile.

## Recommended product direction

Keep two bounded presentation modes instead of replacing one with the other.

### Compact

Use the existing all-at-once board only when all of these are true:

- no more than three short questions;
- no conditional question;
- no long option descriptions or substantial free-text input; and
- the questions and primary action fit comfortably in one view.

### Guided

Use one question per step for longer, conditional, or explanation-heavy work. Treat one multi-select group as one question, not several steps.

- Show the current question and a stable progress cue at the top.
- Make each native radio or checkbox row easy to target without copying the reference UI's distant right-edge checkbox pattern.
- Use explicit Back and Next actions; do not auto-advance after a radio selection.
- Show an explicit Skip action on every question by default, including required questions, and preserve that choice separately from an unanswered field.
- Keep explanation next to the current question. Let the user either pause now or mark that question `Decide after explanation` and finish the remaining questions first.
- End with a complete answer review before the single final submission.
- Preserve one in-flight host request and the current unconfirmed/manual-retry contract.

For a fixed path, `2 / 5` is understandable. When conditions can change the path length, use stable phase wording such as `Baseline → Details → Review` rather than a denominator that moves backward.

## Implementation sequence

### Phase A — Guided navigation without branching — implemented locally

Introduce guided navigation as a candidate schema-version-2 presentation while continuing to accept schema-version-1 compact boards. Prove the interaction before adding conditional answer semantics:

1. Render all controls once in one fragment and reveal only the active question.
2. Add Back, Next, explicit Skip, current-question validation, and a final review.
3. Preserve draft answers while moving between steps.
4. Add `presentation: "stepper"`, include `active_question_id` in explanation requests, and restore through `initial_question_id` so explanation returns to the same step.
5. Verify focus movement, keyboard use, explanation resume, retry, light/dark themes, and 320/736px reflow.

The implementation now uses schema version 2 with `presentation: "stepper"`, a renderer-generated `flow_digest`, and optional restored question/skip/deferred state. It renders every control once, keeps inactive questions `hidden`, validates only the current question on Next, and derives review and output from the same collected answers. Skip and deferred explanation are separate explicit states. Immediate explanation restores the full board; after-completion explanation sends all finished context once and later renders only unresolved questions.

Local evidence:

- 19 Python tests pass, including compact-v1 regression, guided normalization, explicit skip/deferred restoration, parent-linked completion boards, stable flow identity, and fail-closed branch-field rejection.
- Both the existing compact browser smoke test and the new guided browser smoke test pass in local Chrome.
- The guided browser test covers one-visible-question behavior, no auto-advance, current-step error focus, Back preservation, required and optional Skip, skipped-state replacement, immediate and deferred explanation, provisional-answer editing, complete review, retry identity, restored state, host errors, and 320/736px light/dark layouts. The compact test also verifies the parent-linked unresolved-question completion payload.
- Codex Desktop returned a valid five-question submission, preserved answers through Back, and later returned an immediate explanation callback after a required Skip was replaced by a real answer. The replacement board was generated with the same flow identity; its final send was not exercised because the session moved into deferred-flow design.

### Phase A.1 — Deferred explanation without repeating completed questions — implemented locally

- The immediate-explanation action keeps the existing pause-and-restore path.
- The defer-and-continue action stores a question-specific request and optional provisional value without treating it as final.
- Review distinguishes answered, skipped, and decide-after-explanation states. A deferred review sends an explanation request rather than a completed submission.
- After explaining, render only the deferred questions: compact for one to three, otherwise guided with further deferral disabled.
- The small board carries the parent form ID, explanation-request submission ID, and original flow digest. Merge only after all parent fields and deferred question IDs match.
- Local schema and Chrome checks pass. The remaining evidence is one live after-completion callback followed by its small completion-board submission.

### Phase B — Bounded conditional skipping

Do not silently add conditional required-answer semantics to schema version 1. Extend the candidate schema version 2 from Phase A with bounded `show_if` rules before release.

The exact current gate, clear-hidden state rule, explanation restriction, return parity, and implementation order now live in [`BRANCHING_PHASE_B_PLAN.md`](BRANCHING_PHASE_B_PLAN.md). Until those gates are complete, the existing renderer rejection remains intentional.

Candidate version-2 limits:

- at most one `show_if` per question;
- a condition may reference only an earlier `single` question;
- the only initial predicate is `answer_in` with known option values;
- self, forward, text, multi, nested AND/OR, and cyclic conditions are rejected.

When an earlier answer hides a later question, clear that hidden question to its neutral value and remove its Other text. Hidden required questions do not block submission and never appear in the readable summary. The canonical payload should keep every known question ID with neutral values for hidden questions so the receiver can recompute the active path and fail closed on a stale hidden answer.

## Depth without questionnaire bloat

Use follow-up questions only when an answer is ambiguous, conflicting, or materially changes the result. The earlier suggestion of roughly seven guided steps was a UX heuristic, not a renderer limit. Fixed guided and bounded branching now have no arbitrary question-count ceiling, while clear answers should still avoid redundant follow-ups.

Examples of useful triggers:

- `Other` needs one targeted clarification;
- `it depends` needs the deciding condition;
- two selected answers conflict and need priority;
- a high-impact choice lacks the context needed for a safe recommendation.

Do not turn every answer into another question merely because branching is available.

Keep two kinds of adaptation separate:

- **Local guided branching** chooses among questions already declared in one board. It is fast and creates one final conversation submission. It is the leading direction for longer boards, but its default threshold remains to be tested.
- **Model-driven interviewing** sends partial answers back to Codex so the model can invent the next question. It can go deeper, but it creates extra confirmations, turns, latency, and context cost. Treat it as a separate explicitly invoked workflow that may use Choice Board as its input surface, not as the default renderer behavior.

## Mobile fallback

The task cannot reliably detect whether the user is currently viewing a mirrored task on desktop or mobile. When the user reports mobile use or a raw visualization directive, switch to numbered plain text and preserve:

- single versus multiple selection;
- Other;
- optional versus required questions;
- explanation requests; and
- the same normalized answer meaning.

Do not emit another inline board in that state.

## Still open

- Whether guided should always be the default or selected automatically by the compact eligibility rule. The skill currently chooses deliberately and does not persist an automatic threshold.
- Whether the final review later needs direct Edit actions for every answer. Phase A intentionally uses Back-only sequential correction.
- Whether phase progress or numeric progress feels clearer before conditional branches are enabled.
- Whether a separate clear action is ever useful in addition to Skip. Phase A uses Skip as an explicit answer state on every question by default; returning with Back and choosing an answer replaces that state.
- Whether people prefer the full defer-and-continue label or a shorter label after the first deferred live run.

## First prototype acceptance

The original five-question fixed-path acceptance now covers final submission, Back, Skip replacement, and the immediate explanation callback. The next live fixture should defer one unanswered required question and one provisional choice, edit the provisional choice after Back, submit the explanation request from review, and close through the small completion board.
