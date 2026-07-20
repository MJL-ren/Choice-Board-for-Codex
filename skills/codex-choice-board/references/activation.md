# Activation modes

Read this file only for an activation view or change, or for ambient loading without a direct board request. A direct skill-name or natural-language board request is already explicit invocation.

## Modes

- `explicit` (default): run only for a direct board request or deliberate delegation.
- `suggest`: on a good ambient candidate, ask once before opening.
- `auto`: open immediately on a good ambient candidate.

Never suggest or auto-open for secrets, sensitive personal data, a short yes/no question, or final approval for a destructive or external action. Activation decides whether a board may appear; presentation routing happens afterward. A per-request branching or fixed-flow instruction governs only that board.

Map natural settings requests as follows:

- "Use it only when I call it" -> `explicit`
- "Ask me first when it would help" -> `suggest`
- "Open it automatically when it fits" -> `auto`
- "What is the current setting?" -> `show`

Run:

```text
python scripts/set_activation.py <explicit|suggest|auto|show>
```

For ambient routing, run `show --json` and use `effective_mode`, never `configured_mode`. Missing, invalid, duplicate, or inconsistent state fails closed to `explicit`.

`policy.allow_implicit_invocation` stays `true` in every mode so direct natural-language requests remain discoverable. The verified runtime setting controls ambient suggestion or automatic opening; do not infer a mode from the outer policy.

The helper writes and reads back both activation surfaces. Do not report success unless they verify. After a change, say briefly that a new task or Codex restart may be needed before existing task metadata refreshes.
