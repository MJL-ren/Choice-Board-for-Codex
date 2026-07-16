# Activation modes

Keep one skill installation and let the user choose how readily it appears.

## Modes

- `explicit` — default. Run only when the user names the skill, asks for a choice board, or another workflow deliberately delegates a board specification.
- `suggest` — when a request is a good board candidate, ask for permission in one short sentence. Open the board only after the user agrees.
- `auto` — open the board immediately when a request is a good candidate.

Never suggest or auto-open for secrets, sensitive personal information, a short yes/no question, or final approval for destructive or external actions.

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

For implicit routing, run `show --json` and use `effective_mode`, not `configured_mode`. The helper compares the stored mode with the outer Codex policy. Any missing, invalid, duplicate, or mismatched value produces `effective_mode: explicit`.

The helper updates both the user setting and `agents/openai.yaml`. The outer policy and inner mode have different jobs:

- `policy.allow_implicit_invocation: false` prevents implicit skill injection but still allows `$codex-choice-board`.
- `true` only permits implicit injection. The runtime mode still decides whether to suggest or open.

Missing or damaged settings always resolve to `explicit`. Never claim a change succeeded unless both files were written and read back. A new task or Codex restart may be needed before changed skill metadata is reloaded; say so without exposing file details unless the user asks.
