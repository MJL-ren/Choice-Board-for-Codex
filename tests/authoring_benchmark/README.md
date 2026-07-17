# Choice Board authoring benchmark

This isolated harness compares two ways to translate the same locked questions
into the existing Choice Board renderer input:

- `baseline_current_spec`: the current public schema, with normal defaults
  omitted exactly as production examples allow.
- `draft_compiled_spec`: a small JSON authoring adapter whose option entries are
  ordered `[value, label]` pairs. A deterministic compiler expands it into the
  current public schema before the normal production validator runs.

The Draft format is internal authoring input only. After the scale pilot it was
adopted narrowly for fresh fixed-guided boards, while canonical JSON produced
by `render_board.normalize_spec()` remains the sole runtime and storage
authority.

## Fixture profiles

- `q05`: the first five locked questions, rendered as one normal production
  board.
- `q10`: the original ten-question fixture, rendered as one normal production
  board.
- `q15`: one logical fifteen-question authoring input. The historical harness
  deterministically shards both formats into 12 + 3 after authoring so the two
  arms remain directly comparable. That harness choice is not a current product
  question limit.

`q15` is a synthetic authoring-scale benchmark. Its two-part render time must
not be described as native fifteen-question UI performance; the current
renderer has separate 30-question guided-flow coverage.

## Fairness boundary

- Both tasks in a pair receive the same locked profile fixture and may not
  change wording, IDs, order, question types, options, or flags.
- Both use a fresh WAIT-only Codex task, the configured default model, and
  `high` reasoning.
- The target's first command after the execution grant is `benchmark_run.py
  begin`. It must not read the fixture or contract before that command.
- A target may read only the locked fixture and its own contract. The authority,
  golden result, other contract, and other run directory are hidden by
  instruction.
- Both submissions go through the same strict JSON loader, the same production
  normalizer, the same template, and the same renderer.
- The primary metric is `begin_to_first_submit_ms`: practical first-pass
  authoring latency after the target starts. `begin_to_valid_ms` is the
  repair-aware secondary metric. Both include contract reading, serialization,
  and tool use; neither is a pure model-reasoning measurement.
- `dispatch_to_begin_ms` is reported separately as app/server/task wake-up noise.

One A/B pair is a harness pilot, not enough evidence to replace the current
format. Scale comparisons alternate dispatch order and report option count and
source size as well as question count, because repeated option objects are the
Draft's main expected source of byte savings.

The public aggregate result is recorded in [`RESULTS.md`](RESULTS.md). Raw run
directories, task identities, and environment-specific timing traces remain
local-only.

## Local commands

Regenerate or verify the locked generated files:

```powershell
python tests/authoring_benchmark/scripts/build_fixture.py --write
python tests/authoring_benchmark/scripts/build_fixture.py --check
```

Prepare a profile-specific run with `--fixture-profile q05`, `q10`, or `q15`.
The default remains `q10` so existing pilot commands keep working.

Run the isolated tests:

```powershell
python -m unittest discover -s tests -p "test_authoring_benchmark.py" -v
```

Per-run evidence belongs under `tests/authoring_benchmark/runs/`. The shared
repository `.gitignore` excludes that folder; it is not a public fixture or a
source of product behavior.
