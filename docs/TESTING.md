# Testing Status

Last checked: 2026-07-18

Live Codex Desktop findings and the current edge-path test plan are recorded in [`LIVE_TEST_FINDINGS_2026-07-16.md`](LIVE_TEST_FINDINGS_2026-07-16.md).

## Passed locally

- Skill structure validation with the official skill validator.
- Sixty public Python tests covering schema rejection, safe rendering, strict types, marker-safe labels, compact and guided initial-draft validation, answer-note opt-in and restored-state validation, explicit guided skip/deferred state, parent-linked completion boards, fixed guided flow identity, fail-closed activation modes, internal Draft compilation, the 5/10/15 authoring benchmark, bounded branch normalization, restore, sibling fan-out, receiver-parity and fixed-digest oracles, compact three-question enforcement, thirty-question guided authoring, and unsupported-locale English fallback.
- Activation tests verify that natural-language discovery remains enabled in `explicit`, `suggest`, and `auto`, while the validated inner mode still fails closed to direct requests when settings are missing, invalid, or inconsistent.
- The shipped internal Draft compiler now verifies exact equivalence with direct canonical authoring, deterministic repeated output, duplicate-key and non-finite-number rejection, unknown state/branch-field rejection, malformed-pair rejection, and preservation of an existing destination after a failed compile.
- The authoring benchmark records twelve first-pass target runs across two counterbalanced pairs each at 5, 10, and 15 logical questions. Every pair produced exact canonical and rendered equality. Minimal Draft used about 15% fewer semantic input bytes and showed a modest local authoring-time signal, but pair noise prevents any speed guarantee. The public aggregate is in [`../tests/authoring_benchmark/RESULTS.md`](../tests/authoring_benchmark/RESULTS.md).
- The bounded branch runtime accepts only one-layer earlier-single `show_if`, canonicalizes `answer_in`, preserves the exact fixed-guided digest, clears hidden state without revival, and independently recomputes returned active paths.
- Headless Chrome behavior smoke test covering:
  - required-answer errors and focus movement;
  - `Other` show/hide behavior without deleting typed text;
  - completed submissions versus explanation requests, including readable draft summaries;
  - a clearly separated `Data for Codex` text block while preserving the adjacent marker-plus-JSON parser contract;
  - duplicate-click suppression while one host request is in flight;
  - fulfilled-but-unconfirmed, thrown-error, and `{ isError: true }` recovery;
  - byte-identical retry with stable `submission_id`, plus a new ID after edits;
  - restored radio, checkbox, text, and Other draft values without focus theft;
  - missing host API fallback;
  - 320px and 736px layouts;
  - computed Codex/Visualize light and dark theme changes.
- A separate headless Chrome guided-flow smoke test covering:
  - exactly one visible question and no selection-triggered auto-advance;
  - current-step validation and native-control focus;
  - Back preservation across single and multi choices;
  - explicit Skip on required and optional questions, canonical skipped-question IDs, and replacing a skipped state by answering after Back;
  - complete review, Back-only sequential correction, and one final schema-v2 submission;
  - the same human-readable versus automatic-data separation in guided submissions;
  - explanation requests with `active_question_id` and stable `flow_digest`;
  - immediate versus after-completion explanation modes, required unanswered deferral, provisional-answer preservation, Back editing, and ordered question-specific requests;
  - a parent-linked compact completion submission that returns only the unresolved question;
  - restored draft position and focus;
  - thrown-error, `{ isError: true }`, unconfirmed delivery, byte-identical retry, and double-click suppression;
  - 320px and 736px review layouts in host light and dark themes.
- A separate compact-and-guided answer-note smoke test covering:
  - a collapsed note control that appears only after a single or multi selection;
  - preserving a note while switching valid choices and clearing it after the final multi selection is removed or Skip is used;
  - distinct `Other` text and `answer_notes` / `draft_answer_notes` payloads;
  - readable summary and review parity, Back preservation, validated restored notes without focus theft, exact retry identity, a new ID after editing, and 320px light/dark layout checks;
  - legacy note-disabled boards continuing to omit note maps from their callback payloads.
- A separate bounded-branch browser smoke test covering:
  - quick/deep active paths, Next/Back/review Back, and a denominator-free stable progress label;
  - immediate answer, Other, answer-note, validation, Skip, and deferred-state clearing when a target becomes hidden, with no value revival after reactivation;
  - branch-source immediate explanation with deferred explanation unavailable;
  - active-only validation, review, readable summary, and exact `active_question_ids` in submission and explanation callbacks;
  - neutral hidden answers with no hidden auxiliary state;
  - 320px layout for quick and deep paths in host light and dark themes.
- A separate locale-and-scale browser smoke test covering:
  - English compact UI and follow-up output with no Hangul leakage;
  - a thirty-question English fixed-guided board, all thirty steps, complete review, and canonical skipped-ID return without splitting;
  - an unsupported French locale normalized to the English UI fallback while preserving French question content;
  - a two-question bounded branch, proving that branch routing is independent of the fixed-question count boundary.

The browser smoke tests run with the fragment's root-scoped styles and an
existing local Chrome or Playwright browser. Individual scripts can also receive
an installed Visualize stylesheet for closer host styling. They do not contact
an external service or send a real follow-up.

## Reproduce the browser checks

The public runner renders every required fixture into a temporary directory and
then executes the five browser regression scripts. Generated HTML is deleted at
the end of the run.

```powershell
npm install
npx playwright install chromium
npm run test:browser
```

To use an existing local Chrome instead of downloading Playwright Chromium, set
`CHOICE_BOARD_BROWSER` to the browser executable before the final command.

## Still required before release

- Activation metadata reload behavior after changing `explicit`, `suggest`, or `auto` in an installed copy.
- Whether an untagged natural-language “use a choice board” request is treated as an explicit invocation; until verified, `$codex-choice-board` is the guaranteed call form.
- Representative live validation of the conservative automatic branch-selection rule. The one-layer runtime is validated, but automatic model routing has not yet been exercised across several unrelated real requests.
- Clean installation from the public GitHub URL after the prepared changes are committed and pushed.
- Practical host-message behavior beyond the tested thirty-question guided flow; the skill no longer imposes an arbitrary fixed count, but unusually large free-text boards may still meet host or fragment-size limits.

## Confirmed live

- Three consecutive ordinary submissions returned to the same conversation with distinct form IDs.
- Korean text, punctuation, single choice, multi choice, optional input, and Unicode survived the returned message.
- Required-answer blocking displayed a question-specific message.
- A cancelled explanation confirmation produced no callback; the old board falsely showed `보냈어요` and locked. This failure is preserved in the findings note and is the reason for the new unconfirmed/retry contract.
- The patched cancellation state preserved the visible draft, reported delivery as unconfirmed, and exposed `같은 내용 다시 보내기` instead of locking the board.
- The explicit retry produced an explanation callback whose readable summary contained every selected label.
- The replacement board restored all draft choices, and its final canonical submission matched the explanation draft.
- A mirrored mobile view displayed the raw visualization directive rather than the board. Mobile interactive rendering is therefore recorded as unavailable; text is the fallback.
- The first fixed-guided schema-version-2 board returned one complete five-question submission to the same conversation. Form ID, presentation, question IDs, answer types, option values, readable labels, submission ID, and flow digest all validated.
- The live callback verifies final guided delivery, and the live tester independently confirmed Back preservation. A later combined run returned a canonical immediate explanation request after a required question was skipped, revisited, and answered; its skipped-ID list was empty, proving replacement.
- A six-question guided run deferred one required question until review, returned the other five answers once, explained only the deferred question, rendered a one-question compact completion board, and accepted its answer with an exact matching parent form ID, explanation-request submission ID, and flow digest. The final answer merged without re-asking or resubmitting the completed questions.
- A three-question guided answer-note run returned three notes in both the readable Korean summary and canonical `answer_notes` map. The live tester independently confirmed that the selected answers and notes survived repeated Back/Next navigation. A subsequent lightweight hierarchy pass enlarged question headings, gave the required marker a distinct host validation color, underlined choice hints, and strengthened the collapsed note action without changing payloads or state behavior.
- The first bounded branching board declared 12 questions but activated only the six belonging to the selected `compare` route and common tail. Its readable summary, neutral hidden answers, exact ordered `active_question_ids`, form identity, and flow digest all passed receiver validation in the same conversation.

Passing local tests does not claim support for mobile, Codex CLI, VS Code, Apps SDK, or MCP surfaces.
