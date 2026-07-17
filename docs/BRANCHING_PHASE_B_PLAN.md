# Phase B — bounded local branching

Status: canonical renderer, one active-path runtime, clear-only state,
receiver-parity helper, browser regressions, and the first authorized Codex
Desktop callback are complete. Broader optimization waits for an explicitly
invoked Council and owner review.

## Goal

Let one guided board ask a follow-up that was already declared in the same
canonical spec, without another Codex turn. Keep the fixed guided behavior,
review, explanation, retry, and returned-data checks intact. This is not a
survey builder and does not let the model invent questions during the board.

## First accepted shape

Schema version 2 now accepts this exact bounded runtime shape:

```json
"show_if": {
  "question_id": "activity_type",
  "answer_in": ["outdoor", "mixed"]
}
```

- One `show_if` at most per target question.
- Only `question_id` and `answer_in` are allowed.
- The source is an earlier, unconditional `single` question.
- `answer_in` is a non-empty unique list of real source option values. Other,
  neutral, self/forward references, text/multi sources, conditional sources,
  AND/OR, and nested branches are rejected.
- Multiple listed values mean OR.
- A neutral, skipped, or Other source keeps the target hidden.
- Mermaid may later visualize a canonical flow, but is never runtime authority
  or an accepted authoring input.

The first candidate fixture is
`tests/fixtures/board-ko-guided-branch-candidate.json`. The independent rule and
path oracle is `skills/codex-choice-board/scripts/branch_rules.py`. The normal
renderer accepts the fixture because the local gates below now pass together.

## Clear-only state

When an on-screen source change hides a target, immediately clear its answer,
Other text, answer note, Skip state, deferred explanation, and validation error. Never cache
or revive those values when the target becomes active again.

Restored external state is different: a hidden target may carry only its
type-neutral value in `initial_answers`. Non-neutral answers, Other text, answer
notes, Skip, deferred requests, and active position fail closed instead of being
silently repaired.

Hidden required questions do not block the active path. They stay neutral in
canonical answer data and do not appear in review or the readable summary.

## Explanation boundary

A branch-source question may request an immediate explanation, but cannot be
marked `Decide after explanation` in the first prototype. Resolving that source
in a small completion board could activate a new child that the bounded
completion flow never asked. Supporting that would require a separate full-flow
re-entry design.

An active non-source question may still use deferred explanation. If a source
change hides that target, its pending explanation is cleared with the answer.

## Return and receiver parity

Branching submissions and explanation requests will add ordered
`active_question_ids`. The receiver recomputes the list from the known canonical
spec, source answers, and `flow_digest`, then requires an exact match.

- All active and only active questions appear in readable review/summary.
- Every hidden question remains neutral in `answers`.
- Hidden IDs cannot appear in Other, Skip, deferred, or active-position state.
- The current active question must belong to `active_question_ids`.

No separate hidden list or path digest is needed for the first prototype.

## Progress and accessibility

Keep numeric progress for fixed guided boards. A branching board uses stable
wording such as `Question 2 · later questions depend on your answers`, so the
denominator never appears to move backward.

Hidden sections use the native `hidden` state and leave the accessibility tree.
A polite live region announces that later questions changed. Choosing an option
does not auto-advance; Next moves focus to the next active question.

## Implementation gates

1. Lock fixed-guided digest and existing Python/browser regressions.
2. Integrate the rule validator into schema normalization, including invalid
   source/predicate and restored-state failures.
3. Include normalized `show_if` in `flow_digest`; keep digest unchanged for
   existing fixed boards.
4. Add one shared JavaScript active-path helper and clear-only reconciliation.
5. Route navigation, validation, review, summary, explanation, and payload
   creation through that same helper.
6. Add `active_question_ids` and independent receiver-parity vectors.
7. Verify source immediate explanation, target deferred explanation, Back/Next,
   retry identity, keyboard focus, live announcement, 320/736px layout, and
   light/dark themes.
8. Run one authorized Codex Desktop live board before calling branching live validated.

Model-driven interviewing, multi-level branching, arbitrary predicates, hidden
value caches, Mermaid parsing, and automatic question generation remain outside
Phase B.
