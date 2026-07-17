# Contributing

Choice Board is intentionally small: one skill, one deterministic renderer, and
one fixed interaction fragment. Contributions should strengthen that boundary
rather than turn it into a hosted form platform.

## Before changing code

1. Read [`AGENTS.md`](AGENTS.md), [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md),
   and the relevant schema section.
2. Keep project-specific questions and business rules outside the generic skill.
3. Do not commit task IDs, user answers, generated boards, benchmark run folders,
   credentials, or private screenshots.

## Local checks

Python 3.10 or newer is required. Browser checks use Node.js 20 or newer and
Playwright.

```powershell
npm install
python -m unittest discover -s tests -p "test_*.py" -v
npm run test:browser
```

Run the official skill validator available in your Codex installation against
`skills/codex-choice-board`. If a change affects the fragment, state, or follow-up
payload, run the matching browser smoke test described in
[`docs/TESTING.md`](docs/TESTING.md).

## Pull requests

- Explain the user problem first.
- List the exact supported behavior that changes.
- Include the tests run and any host checks that remain unverified.
- Keep generated output and local evidence out of the diff.
- Do not broaden platform, accessibility, privacy, or delivery claims beyond the
  evidence included with the change.
