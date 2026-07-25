# Readable Summary False-Rejection Improvement Plan

- Status: implemented and locally validated; commit and push not performed
- Date: 2026-07-26
- Scope: returned-envelope validation and response recovery only
- Success condition: a presentation-only question-label drift must not consume
  another user turn, while answer, auxiliary text, identity, and branch
  conflicts continue to fail closed

## Incident finding

### Confirmed cause

The renderer and Codex host callback did not introduce the observed drift.

1. The canonical JSON contained the original single-line Korean question label.
2. The rendered HTML embedded that same label and the expected flow digest.
3. A headless replay of the saved HTML captured the exact prompt passed to
   `sendFollowUpMessage`; the readable summary still contained the canonical
   label and the payload contained the expected answer value.
4. The actual user message preserved in the source Codex task also contained
   the canonical label.
5. The assistant-created `.returned.md` copy changed one Korean particle in the
   question label (`도` to `가`). The machine payload and displayed selected
   option remained unchanged.
6. Both the installed and repository validators then reproduced the documented
   hard failure because `_validate_readable_summary()` requires the entire
   reconstructed prefix to match byte-for-byte.

The confirmed defect is therefore a lossy model transcription between the
actual arriving message and the validator input file. The validator correctly
detected that its local input was not an exact copy, but the recovery contract
incorrectly converted that local capture problem into a request for the user to
confirm the choices again.

### Likely contributing cause

`response-handling.md` asks the model to copy a long mixed prose/JSON message
exactly into a file. That manual model-authored file operation is a fragile
transport step. Natural-language cleanup can occur even when the instruction
says “exact,” especially in a long multilingual summary.

The current error is also too coarse. It reports only that the readable summary
does not match, so the receiver cannot distinguish a changed question label
from a changed selected option, Other answer, note, missing question, or local
copy corruption.

### Unverified host behavior

This incident provides no evidence that the host rewrote the callback. The
static browser capture and the actual task message both matched the canonical
label. The host request bytes were not independently captured at a network
boundary, so byte preservation across every Codex Desktop version, locale, and
message size remains unverified.

## Current guarantees and the over-validation point

The machine payload and readable summary serve different purposes.

### Machine payload

The validator currently checks:

- exact marker and payload kind;
- schema version and exact field set;
- form identity;
- question IDs, answer types, and allowed option values;
- Other text and answer-note state;
- required, Skip, deferred-explanation, completion-parent, and active-branch
  state;
- presentation mode and `flow_digest`;
- `submission_id` shape, exact duplicate handling, and conflicting ID reuse.

These checks protect the state-machine and canonical answer contract.
`flow_digest` identifies the normalized guided flow; it does not authenticate
the answer values or readable prose. `submission_id` supplies retry and
duplicate identity; it is not a signature.

### Readable summary

The summary lets the user inspect what will be acted on and gives the receiver a
second representation of answer-bearing content. That redundancy is valuable:
if a copied payload value says one option while the readable selected-option
label says another, the validator should not guess.

The over-validation is treating every byte of the presentation prefix as part
of that answer-integrity check. A question label is already known from the
canonical spec and is not an answer. Requiring its byte identity catches local
transcription drift but does not justify asking the user to choose again when
all answer-bearing content remains exact.

## Required mismatch policy

| Mismatch class | Result | Reason |
| --- | --- | --- |
| Exact summary | Accept | Existing normal path |
| Question-label text or punctuation only, with exact question order and exact answer-bearing content | Accept with a structured presentation warning | Canonical spec supplies the authoritative question label |
| CRLF/LF transport normalization | Accept on the exact path after deterministic normalization | Line-ending encoding is not answer content |
| Selected option display label differs while the payload value is unchanged | Hard fail | The readable cross-check for the coded choice no longer agrees |
| Text answer, Other text, answer note, Skip, or deferred explanation text differs | Hard fail | User-authored or answer-bearing content conflicts |
| Question missing, added, duplicated, or reordered | Hard fail | The summary can no longer be mapped to the canonical answer sequence safely |
| Heading, delimiter, marker, payload shape, form, flow, completion parent, branch state, or submission identity differs | Hard fail | Protocol or state identity is inconsistent |

Arbitrary fuzzy matching and language-specific grammar rules are out of scope.
The validator must not decide whether two sentences “mean the same thing.”

## Recommended minimum change

### 1. Keep the exact fast path

Preserve the current byte-exact prefix comparison as the first check. Existing
valid envelopes retain the same behavior and cost.

### 2. Add one deterministic presentation classifier

Only after the exact check fails, compare the prefix against a canonical
summary shape:

- require the exact heading, horizontal-rule boundary, question count, and
  canonical active-question order;
- for each question, permit only the single-line question-label span to vary;
- require the exact separator and exact reconstructed answer display,
  including selected option labels, text answers, Other text, Skip/deferred
  copy, and answer notes;
- normalize line endings through the existing message parser before this
  second check;
- reject extra or missing summary blocks;
- never inspect linguistic similarity.

If this shape matches, return a non-fatal
`presentation_integrity.status = "question_label_drift"` with bounded mismatch
records containing `question_id`, `expected_label`, and `actual_label`.
Otherwise, keep a hard failure and report the first structural or
answer-bearing mismatch kind and question ID.

The validator CLI should exit zero for this one warning class, print a visible
warning, and include the structured status in `--output` JSON. The validated
canonical payload remains unchanged.

Suggested internal result shape:

```json
{
  "presentation_integrity": {
    "status": "question_label_drift",
    "mismatches": [
      {
        "kind": "question_label",
        "question_id": "example_question",
        "expected": "<canonical label>",
        "actual": "<returned label>"
      }
    ]
  }
}
```

This is validator output, not a callback-payload field.

### 3. Correct the recovery contract

Update `response-handling.md` so a readable-summary failure does not
immediately become a user confirmation request.

The receiver should:

1. treat the actual arriving task message as the source and the
   `.returned.md` file as a fallible local capture;
2. on any summary mismatch, compare the local copy with the original arriving
   message and recapture once before blaming the envelope;
3. continue without a user turn when the validator reports only
   `question_label_drift`, using canonical labels and the validated payload;
4. ignore the drifted label when interpreting the answer and retain the warning
   as diagnostic evidence;
5. ask the user only when the actual arriving message has an answer-bearing or
   protocol conflict, or when the original message cannot be recovered safely.

The always-loaded `SKILL.md` need not grow. It already conditionally routes real
envelopes to `response-handling.md`.

## Alternatives considered

### Keep exact rejection and only tell the model to copy more carefully

This preserves the strongest presentation check but does not remove the
fragile transcription step. The observed failure happened despite an explicit
exact-copy instruction, so wording alone is not an adequate fix.

### Treat every summary mismatch as a warning

This is simpler but removes the useful independent check on selected option
labels, Other text, notes, and text answers. A copied payload could then silently
disagree with what the readable message says. Reject this option.

### Add a summary digest to the payload

A digest has no secret and can be recomputed by anyone editing the message. The
validator can already reconstruct the expected summary from the spec and
payload, so a new digest duplicates information without authenticating it. It
would also change the callback contract. Reject for this fix.

### Add hidden question IDs to every readable line

Stable IDs would simplify parsing but would change renderer output and the
visible-message protocol. Keep this as a later fallback only if the narrow
label-span classifier proves ambiguous in real fixtures.

### Make the host-returned prompt directly authoritative

That would be preferable if Codex exposed a stable, machine-readable API for
the exact current user-message bytes. No such supported interface is established
for this skill. Do not add a new subsystem around unverified host internals.

## Expected implementation impact

### Repository source

Expected changes:

- `skills/codex-choice-board/scripts/validate_envelope.py`
  - exact fast path, narrow classifier, structured diagnostics;
- `tests/test_validate_envelope.py`
  - warning and hard-failure matrix;
- `skills/codex-choice-board/references/response-handling.md`
  - local-capture recovery and no-reconfirmation rule;
- `docs/PROJECT_BRIEF.md`
  - clarify that answer-bearing summary content must agree while safe
    presentation-only label drift is diagnostic;
- `docs/TESTING.md`
  - record the new regression and forward-test evidence after implementation.

Not expected to change:

- `skills/codex-choice-board/SKILL.md`;
- `skills/codex-choice-board/references/schema.md`;
- `skills/codex-choice-board/scripts/render_board.py`;
- `skills/codex-choice-board/assets/choice-board-template.html`;
- callback markers, canonical payload fields, `flow_digest`, or
  `submission_id`.

### Installed skill

After source validation and owner-authorized implementation, synchronize only
the changed installable files, expected to be:

- `scripts/validate_envelope.py`;
- `references/response-handling.md`.

Do not use the current installed copy as the implementation source.

## Compatibility and versioning

- No callback schema bump is required.
- No renderer or HTML migration is required.
- Existing exact compact, guided, branching, explanation, completion, retry,
  and duplicate messages retain their current path.
- Existing hard failures for value, auxiliary state, branch state, identity,
  and conflicting ID reuse remain hard failures.
- The new structured presentation result is validator metadata only.
- Legacy missing-submission-ID behavior remains unchanged and still cannot
  claim duplicate protection.

## Test plan

### Unit tests

Add focused cases for:

1. exact compact and guided summaries returning `status = "exact"`;
2. one and multiple question-label substitutions returning exit zero with
   bounded warning records;
3. safe line-ending normalization;
4. selected option display text changed with unchanged payload value;
5. text answer, Other text, and answer-note changes;
6. missing, extra, duplicate, and reordered summary questions;
7. Skip and deferred-explanation display conflicts;
8. compact, fixed guided, bounded branching, immediate explanation,
   after-completion explanation, and completion-board paths;
9. existing marker, form, flow, active-path, parent, and submission-ID failures;
10. exact duplicate and conflicting reused-ID behavior.

Use sanitized fixtures. Do not commit the incident task message, answers, task
IDs, visualization directory, or other private runtime evidence.

### Integration and regression

- Reproduce the local incident copy: it must validate with
  `question_label_drift`, retain the canonical answer value, and require no
  user confirmation.
- Replay the saved HTML in headless Chrome and confirm the outgoing prompt
  still uses the canonical label.
- Run the full Python discovery suite.
- Run the official skill validator.
- Run all five browser suites even though the renderer is expected to remain
  unchanged.
- Run `git diff --check`.
- After authorized installed-copy synchronization, compare tracked payload
  hashes and run the same validator case against both source and installed
  scripts.

### Codex Desktop forward tests

1. Submit a non-sensitive four-or-more-question guided board and confirm the
   actual arriving message validates as `exact`.
2. Make a controlled local capture with only a question-label change and
   confirm validated-with-warning behavior without another user turn.
3. Make a controlled local capture with a selected-option label change and
   confirm hard failure.
4. Repeat one compact and one bounded-branch submission to ensure the recovery
   path does not weaken question-count or active-path checks.
5. Record host behavior as observed evidence only; do not claim network-byte
   identity without a supported capture surface.

## Acceptance criteria

Implementation is acceptable only when all of the following are true:

1. The reproduced label-only incident no longer asks the user to confirm the
   same choices again.
2. The validator identifies the affected question and classifies the mismatch
   as presentation-only.
3. The returned canonical answer value, Other text, notes, Skip/deferred state,
   branch path, form, flow, and submission identity still pass their existing
   exact checks.
4. Any selected-option, free-text, Other, or note disagreement remains a hard
   failure.
5. Missing, extra, duplicated, or reordered questions remain a hard failure.
6. Conflicting `submission_id` reuse, canonical payload tampering, and invalid
   hidden-branch state remain fail closed.
7. No fuzzy, locale-specific, or model-based semantic comparison is added.
8. Compact, guided, branching, explanation, completion, retry, and duplicate
   regression suites pass.
9. Source and installed skill payloads are synchronized only after source gates
   pass and owner authorization is present.

## Implementation evidence

Completed on 2026-07-26 without changing the callback schema, renderer, HTML
template, or always-loaded `SKILL.md`.

- The exact readable-summary path remains unchanged.
- Question-label-only drift now exits successfully with
  `presentation_integrity.status = "question_label_drift"` and structured
  question-level diagnostics.
- Selected option text, free text, Other text, answer notes, missing or
  reordered questions, branch state, identity, and duplicate conflicts still
  fail closed.
- The focused validator suite passed 15 tests.
- The repository's 82 tracked public Python tests passed; full local discovery,
  including ignored research tests, passed 94 tests.
- The official skill validator passed against both the repository source and
  installed skill.
- All five browser suites passed with local Chrome.
- The preserved incident copy validated with one presentation warning against
  both the source and installed validators, without changing its canonical
  answer.
- All 12 installable source payload files matched the installed copy by
  SHA-256 after synchronization.
- `git diff --check` passed before installed synchronization and is rerun at
  closeout.

No stage, commit, push, tag, release, or repository visibility change is part of
this implementation step.

## Owner decision

No new owner decision is needed for the recommended minimum. It implements the
already stated contract that canonical JSON is authoritative while preserving
hard rejection for answer-bearing disagreement.

Owner approval would be required before broadening warnings to option-label or
arbitrary summary mismatches, adding a callback field or schema version, or
changing renderer output. None of those changes is recommended here.
