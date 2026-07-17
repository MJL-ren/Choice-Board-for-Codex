# Activation modes

Keep one skill installation and let the user choose how readily it appears.

## Modes

- `explicit` — default. Run when the user names the skill, directly asks in natural language for choices or a choice board, or another workflow deliberately delegates a board specification. Examples include “선택지 만들어줘”, “고를 수 있게 보여줘”, and “give me choices”.
- `suggest` — when a request is a good board candidate, ask for permission in one short sentence. Open the board only after the user agrees.
- `auto` — open the board immediately when a request is a good candidate.

Never suggest or auto-open for secrets, sensitive personal information, a short yes/no question, or final approval for destructive or external actions.

Activation mode decides whether a board may appear. It does not choose the board presentation. After a board is authorized, the routing rules in `SKILL.md` may select compact, fixed guided, or bounded branching even while activation remains `explicit`. Per-request wording such as “branch based on my answers” or “show every question without branching” overrides automatic presentation routing for that board only.

## Natural settings requests

Map natural wording to the helper:

- “Use it only when I call it” → `explicit`
- “Ask me first when it would help” → `suggest`
- “Open it automatically when it fits” → `auto`
- “What is the current setting?” → `show`

Run:

```text
python scripts/set_activation.py <explicit|suggest|auto|show>
```

Natural-language direct requests require the skill to be discoverable without a `$` mention, so `policy.allow_implicit_invocation` stays `true` in all three modes. The verified runtime setting decides what happens after loading: `explicit` honors only direct requests, `suggest` may ask first on a matching ambient request, and `auto` may open directly.

For routing without a direct request, run `show --json` and use `effective_mode`, not `configured_mode`. Any missing, invalid, duplicate, or mismatched value produces `effective_mode: explicit`.

The helper updates both the user setting and `agents/openai.yaml`. The outer policy and inner mode have different jobs:

- `policy.allow_implicit_invocation: true` permits natural-language discovery.
- The runtime mode still decides whether a non-direct request may cause a suggestion or automatic board. Do not infer `suggest` or `auto` from the outer policy alone.

Missing or damaged settings always resolve to `explicit`. Never claim a change succeeded unless both files were written and read back. A new task or Codex restart may be needed before changed skill metadata is reloaded; say so without exposing file details unless the user asks.
