# Owner Decision Record

The initial owner choices are resolved. Keep this file as the reasoned decision record; new technical details that can be changed cheaply should not be pushed onto the owner.

## D01 — Invocation policy

- Status: `resolved — explicit by default, configurable afterward`
- Option A — explicit only: run when the user names the skill, directly asks in natural language for choices or a choice board, or when another workflow deliberately delegates a form specification.
- Option B — adaptive automatic: allow Codex to invoke it whenever several answers might be easier to collect visually.
- Decision: Keep **Option A** as the fail-closed runtime default, while offering `suggest` and `auto` as user-controlled modes. Natural-language direct requests such as `선택지 만들어줘` count as explicit invocation, so the outer discovery policy remains enabled in every mode; that policy alone never authorizes ambient suggestion or automatic opening.

## D02 — Visible follow-up format

- Status: `resolved — hybrid`
- Option A — machine-first: show only the marker and compact JSON.
- Option B — hybrid: show a short human-readable answer summary followed by the canonical marker and JSON.
- Decision: Use **Option B**. Keep the readable summary first and the canonical payload compact, without a long visible code block.

## D03 — Public license

- Status: `resolved — MIT`
- Option A — MIT: short and permissive.
- Option B — Apache-2.0: permissive with an explicit patent grant and more text.
- Decision: Use **MIT**.

## D04 — Theme behavior

- Status: `resolved — follow Codex theme`
- Decision: Use Visualize native controls and host theme variables. Do not add a manual theme switch in V0. If the live spike proves that Codex theme propagation fails, reconsider a three-way `system / light / dark` control rather than a two-way override.

## D05 — Unlisted answers and explanation

- Status: `resolved — enabled by default`
- Decision: Choice questions offer `Other` by default, and the board offers a separate “I need more explanation” path. Explanation requests may include drafts but are never completed decisions.

## D06 — Delivery acknowledgement and retry

- Status: `resolved — delivery remains unconfirmed inside the board`
- Decision: A fulfilled `sendFollowUpMessage` call does not prove that a conversation turn exists. Keep the answers available, show an unconfirmed state, and allow only an explicit retry of the byte-identical prompt with the same `submission_id`. Never retry automatically. Identical repeated IDs are duplicate no-ops; conflicting reuse fails closed.

## D07 — Explanation preview and resume

- Status: `resolved — show and restore the current draft`
- Decision: The explanation confirmation includes readable labels for every current draft answer, including Other text. After explaining, re-render the same board with validated `initial_answers` and `initial_other_answers` so the user does not repeat their work.

## D08 — Compact board versus guided questions

- Status: `resolved — count-based fixed routing`
- Option A — compact: show every question together and submit once.
- Option B — guided: show one question at a time, then review all answers before submission.
- Option C — adaptive: keep compact for very short independent forms and use guided for longer, conditional, or explanation-heavy forms.
- Decision: Use compact for one to three fixed questions and guided for four or more fixed questions. Fixed guided has live submission, Back, Skip replacement, immediate explanation, and parent-linked deferred completion evidence. Compact enforces its three-question ceiling; fixed guided and bounded branching have no arbitrary question-count ceiling.

## D10 — Immediate versus deferred explanation

- Status: `resolved — support both in guided mode`
- Decision: Keep immediate pause-and-restore, and add a separate `Decide after explanation` state that lets the user finish other questions first. Deferred values remain provisional and distinct from Skip. After explanation, repeat only unresolved questions in a parent-linked completion board; do not recreate completed questions or finalize the original task before the completion response.

## D09 — Mobile availability

- Status: `resolved — interactive board unavailable, text fallback`
- Decision: Mobile can mirror a desktop task but cannot install Visualize or render the inline Choice Board. When the user reports mobile use or a raw visualization directive, do not render another board. Continue with equivalent numbered text questions in the same conversation. Do not claim automatic device detection.

## D11 — Internal authoring format

- Status: `resolved — Minimal Draft for fresh fixed guided only`
- Decision: Use the shorter option-pair Draft internally when creating a new Korean or English fixed-guided board. Compile it deterministically into normalized canonical JSON before the unchanged renderer. Keep compact, resume, completion, custom-copy, and branching inputs on direct canonical authoring. The Draft is not a public schema or returned-data format.
- Evidence: two counterbalanced runs each at 5, 10, and 15 logical questions all passed first try with exact canonical/render equality. Semantic input was about 15% smaller and local timing showed a modest improvement signal, with enough pair noise that no speed promise is made.

## D12 — First branching boundary

- Status: `live validated — conservative automatic routing approved 2026-07-18`
- Direction: one question-level `show_if`, referencing an earlier unconditional single choice with `answer_in` known values. One source may activate sibling targets, but targets cannot become sources. Hidden state is cleared and never revived. Branch sources cannot defer their decision. Normalization, fixed digest, browser path/clear-only behavior, receiver parity, explanation boundary, 320px/light-dark gates, and one six-active-of-twelve live callback pass.
- Routing decision: a user may force or disable branching for one board. Otherwise, use it only when one stable earlier single answer makes at least one preauthored later question actually inapplicable, the complete dependency fits one layer, at least one path avoids a question, and every candidate does not need side-by-side evaluation. Question count, broad scope, narrow/deep wording, or hoped-for token savings alone do not justify branching. If the proof fails, use fixed count routing; if depth two is needed, use a later separate board rather than imitating nesting.
- Detail: [`BRANCHING_PHASE_B_PLAN.md`](BRANCHING_PHASE_B_PLAN.md).

## D13 — Comment attached to a selected answer

- Status: `live validated — visual hierarchy polish implemented`
- Decision: Keep the normal `answers` and `other_answers` shapes unchanged. A choice question may explicitly enable `allow_answer_note`; its optional comment is carried in the parallel `answer_notes` or `draft_answer_notes` map and restored through `initial_answer_notes`.
- Compatibility: The public and Minimal Draft defaults remain `false`, and false is omitted from normalized questions. This preserves old board UI, callback shape, and guided-flow digest. The skill's authoring policy enables it for ordinary new choice questions unless the receiver requires a strictly closed coded answer.
- State: A note needs a real single or multi selection, never satisfies a required answer, survives changing one valid choice to another, and is cleared by Skip or by removing the final multi selection. `Other` text and the answer note may coexist because they mean different things.
- Live evidence: A three-question guided board returned three answer notes in the readable summary and canonical `answer_notes` map. The live tester independently confirmed Back/Next preservation. The follow-up polish keeps behavior unchanged while enlarging the question heading, separating the required marker with the host's validation color, underlining the choice hint, and making the collapsed note action easier to notice.

## Proposed technical defaults that do not need an owner decision now

- Support Codex Desktop with Visualize first. Treat mobile interactive rendering as known unavailable and mark other Codex surfaces unsupported until tested.
- Keep one canonical JSON schema and let both natural-language callers and other skills normalize into it.
- Use one fixed HTML fragment asset plus a small deterministic renderer for schema validation and safe data injection.
- Allow one active board and at most one in-flight host request in V0.
- Use `window.openai.sendFollowUpMessage({ prompt, title })`; treat its completion as a request result, not delivery proof.
- Keep project-specific questions and decisions outside the generic skill.
