# Owner Decision Record

The initial owner choices are resolved. Keep this file as the reasoned decision record; new technical details that can be changed cheaply should not be pushed onto the owner.

## D01 — Invocation policy

- Status: `resolved — explicit by default, configurable afterward`
- Option A — explicit only: run when the user names the skill or explicitly asks for a choice board, or when another workflow deliberately delegates a form specification.
- Option B — adaptive automatic: allow Codex to invoke it whenever several answers might be easier to collect visually.
- Decision: Keep **Option A** as the fail-closed default, while offering `suggest` and `auto` as user-controlled modes. One skill installation owns all three modes.

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

## Proposed technical defaults that do not need an owner decision now

- Support Codex Desktop with Visualize first; mark other Codex surfaces unsupported until tested.
- Keep one canonical JSON schema and let both natural-language callers and other skills normalize into it.
- Use one fixed HTML fragment asset plus a small deterministic renderer for schema validation and safe data injection.
- Allow one active board and one submission in V0.
- Use `window.openai.sendFollowUpMessage({ prompt })` without optional host-specific fields.
- Keep BSA-specific questions and decisions outside the generic skill.
