# Security Policy

## Trust boundary

Choice Board renders local data inside Codex Desktop and requests a follow-up in
the current conversation. It does not operate a server or database. Submitted
answers still become conversation content and are governed by the host product's
normal data handling; this project does not make a separate confidentiality
guarantee.

Canonical JSON and rendered HTML live in the task's host-managed visualization
directory. Codex Desktop may retain those files after submission or app restart,
and a restored board may include draft answer state. The skill does not operate
an answer database and does not copy answers into its installed skill folder,
but it also cannot promise automatic deletion of host artifacts. Treat the
local visualization directory and the conversation as data-bearing surfaces.

Do not use Choice Board to collect passwords, API keys, payment details, private
customer records, or other sensitive personal information. A board response is
input, not authorization for destructive, publishing, payment, deployment, or
external-send actions.

## Reporting a vulnerability

Use GitHub's **Security > Report a vulnerability** flow when it is available for
this repository. Include:

- the affected file and behavior;
- a minimal reproduction without real secrets or personal data;
- the expected safety boundary; and
- whether the issue affects HTML injection, callback validation, state recovery,
  or local file handling.

Do not publish working exploit details in a public issue. If private reporting is
not available, open a short issue asking for a private contact path without
including the exploit.
