from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "tests" / "authoring_benchmark"
SCRIPTS = BENCH_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from benchlib import (  # noqa: E402
    AUTHORITY_PATH,
    BenchmarkError,
    atomic_write_json,
    load_json_strict,
    logical_questions,
    loads_json_strict,
    normalize_logical_spec,
    normalize_spec,
    profile_paths,
)
from benchmark_run import (  # noqa: E402
    AUTHORED_FILE,
    mark_event,
    prepare_run,
    submit_run,
    validate_baseline,
)
from build_fixture import (  # noqa: E402
    authority_for_profile,
    check_outputs,
    generate_outputs,
)
from compare_runs import compare  # noqa: E402
from compile_draft import compile_draft  # noqa: E402


def as_draft(authority: dict[str, object]) -> dict[str, object]:
    draft: dict[str, object] = {
        "draft_version": 1,
        "mode": "guided",
    }
    for key in (
        "form_id",
        "locale",
        "allow_explanation",
        "allow_deferred_explanation",
        "submit_label",
    ):
        if key in authority:
            draft[key] = copy.deepcopy(authority[key])
    questions: list[dict[str, object]] = []
    for question in authority["questions"]:  # type: ignore[index]
        source = copy.deepcopy(question)
        if "options" in source:
            source["options"] = [
                [option["value"], option["label"]] for option in source["options"]
            ]
        questions.append(source)
    draft["questions"] = questions
    return draft


class AuthoringBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.authority = load_json_strict(AUTHORITY_PATH)
        cls.draft = as_draft(cls.authority)

    def prepare_started(
        self, root: Path, name: str, mode: str, fixture_profile: str = "q10"
    ) -> Path:
        run_dir = root / name
        prepare_run(
            run_dir,
            run_id=name,
            mode=mode,
            thread_id=f"thread-{name}",
            source_thread_id="source-test",
            fixture_profile=fixture_profile,
        )
        mark_event(run_dir, "dispatch", f"dispatch-{name}")
        mark_event(run_dir, "begin", f"begin-{name}")
        return run_dir

    def test_generated_fixture_and_golden_are_current(self) -> None:
        self.assertEqual(check_outputs(generate_outputs()), [])

    def test_baseline_and_draft_reach_exact_same_golden(self) -> None:
        golden = load_json_strict(BENCH_ROOT / "GOLDEN_CANONICAL.json")
        baseline = normalize_spec(validate_baseline(self.authority))
        compiled = compile_draft(self.draft)
        drafted = normalize_spec(compiled)
        self.assertEqual(baseline, golden)
        self.assertEqual(drafted, golden)
        self.assertEqual(baseline, drafted)

    def test_all_scale_profiles_reach_their_exact_golden(self) -> None:
        expected_counts = {"q05": 5, "q10": 10, "q15": 15}
        for profile, expected_count in expected_counts.items():
            with self.subTest(profile=profile):
                authority = authority_for_profile(profile)
                golden = load_json_strict(profile_paths(profile)["golden"])
                baseline = normalize_logical_spec(validate_baseline(authority))
                drafted = normalize_logical_spec(compile_draft(as_draft(authority)))
                self.assertEqual(baseline, golden)
                self.assertEqual(drafted, golden)
                self.assertEqual(len(logical_questions(golden)), expected_count)
        q15 = load_json_strict(profile_paths("q15")["golden"])
        self.assertEqual(q15["artifact_kind"], "benchmark_only_logical_bundle")
        self.assertEqual([len(part["questions"]) for part in q15["parts"]], [12, 3])
        self.assertEqual(
            [part["form_id"] for part in q15["parts"]],
            [
                "authoring-benchmark-free-time-15q--part-01",
                "authoring-benchmark-free-time-15q--part-02",
            ],
        )

    def test_q15_rejects_cross_boundary_duplicate_question_id(self) -> None:
        authority = authority_for_profile("q15")
        authority["questions"][12]["id"] = authority["questions"][0]["id"]
        with self.assertRaisesRegex(BenchmarkError, "duplicate question id"):
            normalize_logical_spec(validate_baseline(authority))

    def test_strict_loader_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(BenchmarkError, "duplicate JSON key"):
            loads_json_strict('{"form_id":"one","form_id":"two"}')

    def test_contract_validators_reject_unknown_or_malformed_fields(self) -> None:
        baseline = copy.deepcopy(self.authority)
        baseline["unexpected"] = True
        with self.assertRaisesRegex(BenchmarkError, "unknown baseline top-level"):
            validate_baseline(baseline)

        draft = copy.deepcopy(self.draft)
        draft["unexpected"] = True
        with self.assertRaisesRegex(BenchmarkError, "unknown Draft top-level"):
            compile_draft(draft)

        draft = copy.deepcopy(self.draft)
        draft["questions"][0]["options"][0] = ["value-only"]
        with self.assertRaisesRegex(BenchmarkError, "must be \[value, label\]"):
            compile_draft(draft)

    def test_reserved_and_duplicate_values_fail_in_production_normalizer(self) -> None:
        for replacement, message in [
            ("__other__", "reserved"),
            ("one_hour", "duplicate option value"),
        ]:
            draft = copy.deepcopy(self.draft)
            draft["questions"][0]["options"][0][0] = replacement
            if replacement == "one_hour":
                draft["questions"][0]["options"][1][0] = replacement
            with self.assertRaisesRegex(BenchmarkError, message):
                normalize_spec(compile_draft(draft))

    def test_runner_records_equal_outputs_and_compare_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_dir = self.prepare_started(
                root, "baseline", "baseline_current_spec"
            )
            draft_dir = self.prepare_started(root, "draft", "draft_compiled_spec")
            atomic_write_json(baseline_dir / AUTHORED_FILE, self.authority)
            atomic_write_json(draft_dir / AUTHORED_FILE, self.draft)
            baseline_state = submit_run(baseline_dir)
            draft_state = submit_run(draft_dir)

            self.assertEqual(baseline_state["status"], "complete")
            self.assertEqual(draft_state["status"], "complete")
            self.assertEqual(
                (baseline_dir / "CANONICAL.json").read_bytes(),
                (draft_dir / "CANONICAL.json").read_bytes(),
            )
            self.assertEqual(
                (baseline_dir / "BOARD.html").read_bytes(),
                (draft_dir / "BOARD.html").read_bytes(),
            )
            report = compare(baseline_dir, draft_dir)
            self.assertIn("valid pilot pair", report)
            self.assertIn("normalized_canonical_equal: true", report)

    def test_q15_runner_preserves_separate_render_parts_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_dir = self.prepare_started(
                root, "bundle-a", "baseline_current_spec", "q15"
            )
            draft_dir = self.prepare_started(
                root, "bundle-b", "draft_compiled_spec", "q15"
            )
            authority = authority_for_profile("q15")
            atomic_write_json(baseline_dir / AUTHORED_FILE, authority)
            atomic_write_json(draft_dir / AUTHORED_FILE, as_draft(authority))
            baseline_state = submit_run(baseline_dir)
            draft_state = submit_run(draft_dir)

            self.assertEqual(
                baseline_state["result"]["render_artifact_kind"],
                "production_part_bundle",
            )
            self.assertFalse((baseline_dir / "BOARD.html").exists())
            for filename in (
                "BOARD_PART_01.html",
                "BOARD_PART_02.html",
                "RENDER_BUNDLE_MANIFEST.json",
            ):
                self.assertEqual(
                    (baseline_dir / filename).read_bytes(),
                    (draft_dir / filename).read_bytes(),
                )
            report = compare(baseline_dir, draft_dir)
            self.assertIn("fixture_profile: q15", report)
            self.assertIn("ordered production part bytes", report)

    def test_invalid_input_is_preserved_then_one_repair_can_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.prepare_started(
                Path(directory), "repair", "draft_compiled_spec"
            )
            invalid = copy.deepcopy(self.draft)
            invalid["questions"][0]["label"] = "바뀐 문구"
            atomic_write_json(run_dir / AUTHORED_FILE, invalid)
            with self.assertRaisesRegex(BenchmarkError, "differs from locked golden"):
                submit_run(run_dir)
            first_state = load_json_strict(run_dir / "RUN.json")
            self.assertEqual(len(first_state["attempts"]), 1)
            self.assertTrue((run_dir / "attempts" / "attempt-001-input.json").exists())

            with self.assertRaisesRegex(BenchmarkError, "unchanged invalid input"):
                submit_run(run_dir)
            repeated_state = load_json_strict(run_dir / "RUN.json")
            self.assertEqual(len(repeated_state["attempts"]), 1)

            atomic_write_json(run_dir / AUTHORED_FILE, self.draft)
            final_state = submit_run(run_dir)
            self.assertEqual(final_state["status"], "complete")
            self.assertFalse(final_state["result"]["first_pass"])
            self.assertEqual(final_state["result"]["attempt_count"], 2)

    def test_completed_resubmit_is_idempotent_only_for_same_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.prepare_started(
                Path(directory), "idempotent", "baseline_current_spec"
            )
            atomic_write_json(run_dir / AUTHORED_FILE, self.authority)
            first = submit_run(run_dir)
            second = submit_run(run_dir)
            self.assertEqual(first, second)

            changed = copy.deepcopy(self.authority)
            changed["questions"][0]["label"] = "다른 입력"
            atomic_write_json(run_dir / AUTHORED_FILE, changed)
            with self.assertRaisesRegex(BenchmarkError, "cannot accept different"):
                submit_run(run_dir)

    def test_compare_rejects_lock_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_dir = self.prepare_started(
                root, "lock-a", "baseline_current_spec"
            )
            draft_dir = self.prepare_started(root, "lock-b", "draft_compiled_spec")
            atomic_write_json(baseline_dir / AUTHORED_FILE, self.authority)
            atomic_write_json(draft_dir / AUTHORED_FILE, self.draft)
            submit_run(baseline_dir)
            submit_run(draft_dir)
            drifted = load_json_strict(draft_dir / "RUN.json")
            drifted["locks"]["template_sha256"] = "0" * 64
            atomic_write_json(draft_dir / "RUN.json", drifted)
            with self.assertRaisesRegex(BenchmarkError, "run lock differs"):
                compare(baseline_dir, draft_dir)


if __name__ == "__main__":
    unittest.main()
