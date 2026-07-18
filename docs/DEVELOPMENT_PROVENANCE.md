# Development Provenance

This is a public development record, not a claim that the project has been
submitted to a competition.

## Timeline

- OpenAI Build Week submission period opened July 13, 2026 at 9:00 AM PT.
- Choice Board's first Git commit was created July 16, 2026 at 7:36 PM KST.
- The initial delivery-recovery hardening commit followed on July 16 at 9:04 PM
  KST.
- Compact, guided, deferred-explanation, answer-note, internal Draft, and bounded
  branching work in the public preview baseline was developed after those
  commits.
- Public preview baseline commit `7382e2a311ab943bed291d6317b9bc0cc610066b`
  was pushed and made publicly readable on July 18, 2026 after clean-clone,
  isolated-install, Python, official skill-validator, and browser gates passed.

The repository therefore began during the event's submission period. If it is
submitted, the final commit history and primary Codex `/feedback` session ID
should be used as the authoritative evidence.

## How Codex and GPT-5.6 contributed

Codex and GPT-5.6 were used to:

- turn live cancellation and false-delivery behavior into a fail-closed retry
  contract;
- design and revise the canonical input/callback schema;
- implement the deterministic renderer, internal Draft compiler, and one-layer
  branch evaluator;
- generate malformed-input, restore, hidden-state, duplicate, and receiver-parity
  fixtures;
- compare direct canonical authoring with a smaller internal authoring format;
- inspect browser behavior at narrow and desktop widths; and
- keep public claims aligned with verified behavior.

The repository owner made the product decisions: direct-request default,
desktop-only interactive support, plain-text fallback, no-server architecture,
answer-note semantics, deferred-explanation boundary, and the one-layer branch
limit.

## OpenAI Build Week submission checklist

The current official sources are the [event overview](https://openai.devpost.com/),
[Official Rules](https://openai.devpost.com/rules), and
[FAQ](https://openai.devpost.com/details/faqs).

Before any submission:

- [x] Commit and push the public preview baseline.
- [x] Verify an anonymous clean clone and isolated GitHub skill installation.
- [ ] Confirm the Visualize prerequisite is available to a clean judge account,
      or provide an equally clear fallback testing path.
- [ ] Record an English, public, under-three-minute YouTube demo with audio.
- [ ] Explain in the video and submission how Codex and GPT-5.6 were used.
- [ ] Capture the `/feedback` Session ID from the primary build task.
- [ ] Provide the public repository URL, MIT license, install steps, supported
      platforms, and a no-rebuild judge test prompt.
- [ ] Keep submission materials in English or provide an English translation.

The rules expressly allow agent plugins, skills, MCPs, and tools. Visualize is
not named specifically, so its use is not a documented eligibility guarantee or
ban. The practical gate is whether the project installs and runs consistently on
its stated platform and is easy for judges to test.
