from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "codex-choice-board" / "scripts" / "render_board.py"
FIXTURE = ROOT / "tests" / "fixtures" / "board-ko.json"
PREFILLED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-prefilled.json"
GUIDED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided.json"
GUIDED_PREFILLED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-prefilled.json"
GUIDED_DEFERRED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-deferred.json"
COMPLETION_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-completion.json"
ANSWER_NOTES_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-answer-notes.json"
GUIDED_ANSWER_NOTES_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-answer-notes.json"
GUIDED_ANSWER_NOTES_PREFILLED_FIXTURE = (
    ROOT / "tests" / "fixtures" / "board-ko-guided-answer-notes-prefilled.json"
)
BRANCHING_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-branch-candidate.json"


class RenderBoardTests(unittest.TestCase):
    def render(self, spec: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--spec", str(spec), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )

    def normalize_data(self, data: dict[str, object]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "spec.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            fragment = output.read_text(encoding="utf-8")
        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        return json.loads(base64.b64decode(match.group(1)).decode("utf-8"))

    def test_renders_safe_fragment_with_theme_utilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "board.html"
            result = self.render(FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            fragment = output.read_text(encoding="utf-8")

        lowered = fragment.lower()
        self.assertNotIn("<!doctype", lowered)
        self.assertNotIn("<html", lowered)
        self.assertNotIn("<head", lowered)
        self.assertNotIn("<body", lowered)
        self.assertNotIn("fetch(", fragment)
        self.assertNotIn("XMLHttpRequest", fragment)
        self.assertNotIn("WebSocket", fragment)
        self.assertNotIn("__CHOICE_BOARD_SPEC_BASE64__", fragment)
        self.assertIn("form-check-input", fragment)
        self.assertIn("form-control", fragment)
        self.assertIn("btn btn-primary", fragment)
        self.assertIn("window.openai.sendFollowUpMessage({", fragment)
        self.assertIn("CHOICE_BOARD_EXPLANATION_REQUEST", fragment)
        self.assertIn("submission_id", fragment)
        self.assertIn("deliveryUnconfirmed", fragment)
        self.assertIn("changedAfterSend", fragment)
        self.assertIn("draftHeading", fragment)
        self.assertIn("__other__", fragment)
        self.assertIn('input.maxLength = 4000', fragment)
        self.assertIn('if (syncOtherVisibility) syncOtherVisibility(true);', fragment)
        self.assertIn('if (syncAnswerNoteVisibility) syncAnswerNoteVisibility();', fragment)
        self.assertIn('"choice-board-question-heading"', fragment)
        self.assertIn('"choice-board-required text-destructive"', fragment)
        self.assertIn('"text-small choice-board-question-hint"', fragment)
        self.assertIn('element("h3", "choice-board-question-heading")', fragment)

        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertTrue(normalized["allow_explanation"])
        self.assertTrue(normalized["questions"][0]["allow_other"])
        self.assertEqual(normalized["locale"], "ko")
        self.assertEqual(normalized["initial_answers"], {})
        self.assertEqual(normalized["initial_other_answers"], {})
        self.assertNotIn("presentation", normalized)
        self.assertNotIn("flow_digest", normalized)

    def test_normalizes_valid_prefilled_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "board.html"
            result = self.render(PREFILLED_FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            fragment = output.read_text(encoding="utf-8")

        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertEqual(normalized["initial_answers"]["route"], "__other__")
        self.assertEqual(normalized["initial_answers"]["checks"], ["scope", "ownership"])
        self.assertEqual(normalized["initial_answers"]["note"], "복원된 메모")
        self.assertEqual(normalized["initial_other_answers"], {"route": "새 방식"})

    def test_allows_incomplete_required_initial_draft(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["initial_answers"] = {"route": "", "checks": [], "note": "초안"}
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "draft.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_renders_guided_stepper_with_stable_flow_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "guided.html"
            result = self.render(GUIDED_FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            fragment = output.read_text(encoding="utf-8")

        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertEqual(normalized["schema_version"], 2)
        self.assertEqual(normalized["presentation"], "stepper")
        self.assertEqual(normalized["initial_question_id"], "route")
        self.assertEqual(normalized["initial_skipped_question_ids"], [])
        self.assertEqual(normalized["initial_deferred_explanation_requests"], [])
        self.assertTrue(all(question["allow_skip"] for question in normalized["questions"]))
        self.assertRegex(normalized["flow_digest"], r"^sha256:[0-9a-f]{64}$")

        fixture = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        fixture["initial_answers"] = {"route": "pilot"}
        fixture["initial_question_id"] = "tone"
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "guided-restored.json"
            output = Path(directory) / "guided-restored.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            restored_fragment = output.read_text(encoding="utf-8")
        restored_match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', restored_fragment)
        self.assertIsNotNone(restored_match)
        restored = json.loads(base64.b64decode(restored_match.group(1)).decode("utf-8"))
        self.assertEqual(restored["flow_digest"], normalized["flow_digest"])

        fixture["questions"][0]["label"] = "달라진 질문"
        fixture.pop("initial_answers")
        fixture.pop("initial_question_id")
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "guided-changed.json"
            output = Path(directory) / "guided-changed.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            changed_fragment = output.read_text(encoding="utf-8")
        changed_match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', changed_fragment)
        self.assertIsNotNone(changed_match)
        changed = json.loads(base64.b64decode(changed_match.group(1)).decode("utf-8"))
        self.assertNotEqual(changed["flow_digest"], normalized["flow_digest"])

    def test_compact_rejects_more_than_three_questions(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fourth = json.loads(json.dumps(fixture["questions"][-1]))
        fourth["id"] = "extra"
        fourth["label"] = "추가 질문"
        fixture["questions"].append(fourth)
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "compact-too-long.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            result = self.render(spec, output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("compact boards support 1 to 3 questions", result.stderr)

    def test_guided_accepts_thirty_questions_without_splitting(self) -> None:
        fixture = {
            "schema_version": 2,
            "presentation": "stepper",
            "form_id": "guided-thirty-001",
            "locale": "en",
            "questions": [
                {
                    "id": f"q{index:02d}",
                    "type": "text",
                    "label": f"Question {index}",
                }
                for index in range(1, 31)
            ],
        }
        normalized = self.normalize_data(fixture)
        self.assertEqual(len(normalized["questions"]), 30)
        self.assertEqual(normalized["presentation"], "stepper")

    def test_small_bounded_branch_remains_valid_regardless_of_count(self) -> None:
        fixture = json.loads(BRANCHING_FIXTURE.read_text(encoding="utf-8"))
        fixture["questions"] = fixture["questions"][:2]
        normalized = self.normalize_data(fixture)
        self.assertEqual(len(normalized["questions"]), 2)
        self.assertEqual(normalized["questions"][1]["show_if"]["question_id"], "depth")

    def test_unknown_locale_falls_back_to_english(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["locale"] = "fr"
        normalized = self.normalize_data(fixture)
        self.assertEqual(normalized["locale"], "en")

    def test_normalizes_guided_skip_state_without_changing_flow_identity(self) -> None:
        base = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            baseline_spec = Path(directory) / "baseline.json"
            skipped_spec = Path(directory) / "skipped.json"
            baseline_output = Path(directory) / "baseline.html"
            skipped_output = Path(directory) / "skipped.html"
            baseline_spec.write_text(json.dumps(base), encoding="utf-8")
            skipped = json.loads(json.dumps(base))
            skipped["initial_skipped_question_ids"] = ["route", "tone"]
            skipped_spec.write_text(json.dumps(skipped), encoding="utf-8")

            baseline_result = self.render(baseline_spec, baseline_output)
            skipped_result = self.render(skipped_spec, skipped_output)
            self.assertEqual(baseline_result.returncode, 0, baseline_result.stderr)
            self.assertEqual(skipped_result.returncode, 0, skipped_result.stderr)

            baseline_match = re.search(
                r'id="codex-choice-board-spec">([^<]+)</script>',
                baseline_output.read_text(encoding="utf-8"),
            )
            skipped_match = re.search(
                r'id="codex-choice-board-spec">([^<]+)</script>',
                skipped_output.read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(baseline_match)
            self.assertIsNotNone(skipped_match)
            baseline_normalized = json.loads(
                base64.b64decode(baseline_match.group(1)).decode("utf-8")
            )
            skipped_normalized = json.loads(
                base64.b64decode(skipped_match.group(1)).decode("utf-8")
            )

        self.assertEqual(
            skipped_normalized["initial_skipped_question_ids"],
            ["route", "tone"],
        )
        self.assertEqual(
            skipped_normalized["flow_digest"],
            baseline_normalized["flow_digest"],
        )

    def test_normalizes_guided_restored_draft_and_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "guided-prefilled.html"
            result = self.render(GUIDED_PREFILLED_FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            fragment = output.read_text(encoding="utf-8")

        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertEqual(normalized["initial_question_id"], "tone")
        self.assertEqual(normalized["initial_answers"]["tone"], "__other__")
        self.assertEqual(normalized["initial_other_answers"], {"tone": "상황에 맞게"})

    def test_normalizes_deferred_explanation_state_without_changing_flow_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            baseline_output = Path(directory) / "guided.html"
            deferred_output = Path(directory) / "guided-deferred.html"
            baseline_result = self.render(GUIDED_FIXTURE, baseline_output)
            deferred_result = self.render(GUIDED_DEFERRED_FIXTURE, deferred_output)
            self.assertEqual(baseline_result.returncode, 0, baseline_result.stderr)
            self.assertEqual(deferred_result.returncode, 0, deferred_result.stderr)

            baseline_match = re.search(
                r'id="codex-choice-board-spec">([^<]+)</script>',
                baseline_output.read_text(encoding="utf-8"),
            )
            deferred_match = re.search(
                r'id="codex-choice-board-spec">([^<]+)</script>',
                deferred_output.read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(baseline_match)
            self.assertIsNotNone(deferred_match)
            baseline = json.loads(base64.b64decode(baseline_match.group(1)).decode("utf-8"))
            deferred = json.loads(base64.b64decode(deferred_match.group(1)).decode("utf-8"))

        self.assertEqual(
            deferred["initial_deferred_explanation_requests"],
            [{"question_id": "tone", "request": "두 설명 방식의 차이를 알려 줘"}],
        )
        self.assertEqual(deferred["flow_digest"], baseline["flow_digest"])

    def test_normalizes_and_rejects_completion_parent_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "completion.html"
            result = self.render(COMPLETION_FIXTURE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            match = re.search(
                r'id="codex-choice-board-spec">([^<]+)</script>',
                output.read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(match)
            normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertEqual(normalized["completion_parent"]["parent_form_id"], "guided-test-ko")
        self.assertEqual(
            normalized["completion_parent"]["parent_submission_id"],
            "cb-00000000-0000-4000-8000-000000000099",
        )

        guided_completion = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        guided_completion["form_id"] = "guided-test-ko-completion-many"
        guided_completion["completion_parent"] = normalized["completion_parent"]
        for question in guided_completion["questions"]:
            question["allow_skip"] = False
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "guided-completion.json"
            output = Path(directory) / "guided-completion.html"
            spec.write_text(json.dumps(guided_completion), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 0, result.stderr)

        base = json.loads(COMPLETION_FIXTURE.read_text(encoding="utf-8"))
        invalid_cases = [
            ({"parent_form_id": "guided-test-ko"}, "missing completion_parent fields"),
            (
                {
                    "parent_form_id": "guided-test-ko",
                    "parent_submission_id": "wrong",
                    "parent_flow_digest": "sha256:" + ("1" * 64),
                },
                "parent_submission_id is invalid",
            ),
            (
                {
                    "parent_form_id": "guided-test-ko",
                    "parent_submission_id": "cb-valid",
                    "parent_flow_digest": "sha256:bad",
                },
                "parent_flow_digest is invalid",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-completion.json"
            output = Path(directory) / "completion.html"
            for completion_parent, expected in invalid_cases:
                fixture = json.loads(json.dumps(base))
                fixture["completion_parent"] = completion_parent
                spec.write_text(json.dumps(fixture), encoding="utf-8")
                result = self.render(spec, output)
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                if output.exists():
                    output.unlink()

        invalid_guided_completion = json.loads(
            GUIDED_FIXTURE.read_text(encoding="utf-8")
        )
        invalid_guided_completion["completion_parent"] = normalized["completion_parent"]
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-guided-completion.json"
            output = Path(directory) / "guided-completion.html"
            spec.write_text(json.dumps(invalid_guided_completion), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn(
                "guided completion questions must set allow_skip false",
                result.stderr,
            )

    def test_rejects_invalid_or_branching_guided_specs(self) -> None:
        base = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        cases: list[tuple[dict[str, object], str]] = []

        missing_presentation = dict(base)
        missing_presentation.pop("presentation")
        cases.append((missing_presentation, 'requires presentation "stepper"'))

        wrong_presentation = dict(base)
        wrong_presentation["presentation"] = "compact"
        cases.append((wrong_presentation, 'requires presentation "stepper"'))

        unknown_position = dict(base)
        unknown_position["initial_question_id"] = "missing"
        cases.append((unknown_position, "must name a known question"))

        top_level_branch = dict(base)
        top_level_branch["branches"] = []
        cases.append((top_level_branch, "top-level branching fields are not supported"))

        question_branch = json.loads(json.dumps(base))
        question_branch["questions"][0]["show_if"] = {"answer": "x"}
        cases.append((question_branch, "unknown"))

        wrong_digest = dict(base)
        wrong_digest["flow_digest"] = "sha256:" + ("0" * 64)
        cases.append((wrong_digest, "flow_digest does not match"))

        duplicate_skipped = dict(base)
        duplicate_skipped["initial_skipped_question_ids"] = ["route", "route"]
        cases.append((duplicate_skipped, "must not contain duplicates"))

        unknown_skipped = dict(base)
        unknown_skipped["initial_skipped_question_ids"] = ["missing"]
        cases.append((unknown_skipped, "unknown initial skipped question ids"))

        unordered_skipped = dict(base)
        unordered_skipped["initial_skipped_question_ids"] = ["tone", "route"]
        cases.append((unordered_skipped, "must follow question order"))

        answered_skipped = json.loads(json.dumps(base))
        answered_skipped["initial_answers"] = {"route": "pilot"}
        answered_skipped["initial_skipped_question_ids"] = ["route"]
        cases.append((answered_skipped, "must have a neutral initial answer"))

        forbidden_skipped = json.loads(json.dumps(base))
        forbidden_skipped["questions"][0]["allow_skip"] = False
        forbidden_skipped["initial_skipped_question_ids"] = ["route"]
        cases.append((forbidden_skipped, "because allow_skip is false"))

        duplicate_deferred = dict(base)
        duplicate_deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "route", "request": "첫 요청"},
            {"question_id": "route", "request": "둘째 요청"},
        ]
        cases.append((duplicate_deferred, "must not contain duplicates"))

        unknown_deferred = dict(base)
        unknown_deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "missing", "request": "설명"}
        ]
        cases.append((unknown_deferred, "must name a known question"))

        unordered_deferred = dict(base)
        unordered_deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "tone", "request": "둘째"},
            {"question_id": "route", "request": "첫째"},
        ]
        cases.append((unordered_deferred, "must follow question order"))

        overlapping_deferred = dict(base)
        overlapping_deferred["initial_skipped_question_ids"] = ["route"]
        overlapping_deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "route", "request": "설명"}
        ]
        cases.append((overlapping_deferred, "must not overlap"))

        disabled_deferred = dict(base)
        disabled_deferred["allow_explanation"] = False
        disabled_deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "route", "request": "설명"}
        ]
        cases.append((disabled_deferred, "require allow_explanation true"))

        disabled_deferred_mode = dict(base)
        disabled_deferred_mode["allow_deferred_explanation"] = False
        disabled_deferred_mode["initial_deferred_explanation_requests"] = [
            {"question_id": "route", "request": "설명"}
        ]
        cases.append(
            (disabled_deferred_mode, "require allow_deferred_explanation true")
        )

        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-guided.json"
            output = Path(directory) / "guided.html"
            for fixture, expected in cases:
                spec.write_text(json.dumps(fixture), encoding="utf-8")
                result = self.render(spec, output)
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                if output.exists():
                    output.unlink()

    def test_rejects_guided_fields_in_schema_v1(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["presentation"] = "stepper"
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-v1.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("schema_version 1 must omit guided-flow fields", result.stderr)

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["questions"][0]["allow_skip"] = True
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-v1-question.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("allow_skip is supported only", result.stderr)

        for field, value in [
            ("initial_deferred_explanation_requests", []),
            ("allow_deferred_explanation", False),
        ]:
            fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
            fixture[field] = value
            with tempfile.TemporaryDirectory() as directory:
                spec = Path(directory) / "invalid-v1-guided-field.json"
                output = Path(directory) / "board.html"
                spec.write_text(json.dumps(fixture), encoding="utf-8")
                result = self.render(spec, output)
                self.assertEqual(result.returncode, 2)
                self.assertIn("schema_version 1 must omit guided-flow fields", result.stderr)

    def test_rejects_invalid_initial_answers(self) -> None:
        base = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cases = [
            ({"unknown": "apply"}, {}, "unknown initial answer question ids"),
            ({"route": ["apply"]}, {}, "must be empty or a known option value"),
            ({"route": "missing"}, {}, "must be empty or a known option value"),
            ({"checks": ["scope", "scope"]}, {}, "must contain unique known option values"),
            ({"checks": ["missing"]}, {}, "must contain unique known option values"),
            ({"note": []}, {}, "must be a string of at most 4000 characters"),
            ({"note": "x" * 4001}, {}, "must be a string of at most 4000 characters"),
            ({"route": "apply"}, {"route": "orphan"}, "requires __other__"),
            ({"route": "__other__"}, {"route": "x" * 1001}, "at most 1000 characters"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"
            for initial_answers, initial_other_answers, expected in cases:
                fixture = dict(base)
                fixture["initial_answers"] = initial_answers
                fixture["initial_other_answers"] = initial_other_answers
                spec.write_text(json.dumps(fixture), encoding="utf-8")
                result = self.render(spec, output)
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                if output.exists():
                    output.unlink()

            fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
            fixture["questions"][0]["allow_other"] = False
            fixture["initial_answers"] = {"route": "__other__"}
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("must be empty or a known option value", result.stderr)

    def test_answer_notes_are_opt_in_and_restore_without_changing_flow_identity(self) -> None:
        legacy = self.normalize_data(json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8")))
        self.assertNotIn("allow_answer_note", legacy["questions"][0])
        self.assertNotIn("initial_answer_notes", legacy)

        explicit_false = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        explicit_false["questions"][0]["allow_answer_note"] = False
        normalized_false = self.normalize_data(explicit_false)
        self.assertNotIn("allow_answer_note", normalized_false["questions"][0])
        self.assertEqual(normalized_false["flow_digest"], legacy["flow_digest"])

        enabled = json.loads(GUIDED_FIXTURE.read_text(encoding="utf-8"))
        enabled["questions"][0]["allow_answer_note"] = True
        normalized_enabled = self.normalize_data(enabled)
        self.assertTrue(normalized_enabled["questions"][0]["allow_answer_note"])
        self.assertNotEqual(normalized_enabled["flow_digest"], legacy["flow_digest"])

        restored = json.loads(json.dumps(enabled))
        restored["initial_answers"] = {"route": "pilot"}
        restored["initial_answer_notes"] = {"route": "먼저 작게 확인하고 싶어요.\n복구도 챙겨 주세요."}
        normalized_restored = self.normalize_data(restored)
        self.assertEqual(
            normalized_restored["initial_answer_notes"],
            restored["initial_answer_notes"],
        )
        self.assertEqual(
            normalized_restored["flow_digest"],
            normalized_enabled["flow_digest"],
        )

        compact = self.normalize_data(
            json.loads(ANSWER_NOTES_FIXTURE.read_text(encoding="utf-8"))
        )
        self.assertTrue(compact["questions"][0]["allow_answer_note"])
        self.assertNotIn("initial_answer_notes", compact)

        completion = json.loads(ANSWER_NOTES_FIXTURE.read_text(encoding="utf-8"))
        completion["completion_parent"] = {
            "parent_form_id": "guided-parent",
            "parent_submission_id": "cb-00000000-0000-4000-8000-000000000200",
            "parent_flow_digest": "sha256:" + ("2" * 64),
        }
        completion["initial_answers"] = {"direction": "deep"}
        completion["initial_answer_notes"] = {"direction": "완료 보드 메모"}
        normalized_completion = self.normalize_data(completion)
        self.assertEqual(
            normalized_completion["initial_answer_notes"],
            {"direction": "완료 보드 메모"},
        )

        prefilled = self.normalize_data(
            json.loads(GUIDED_ANSWER_NOTES_PREFILLED_FIXTURE.read_text(encoding="utf-8"))
        )
        self.assertEqual(
            prefilled["initial_answer_notes"],
            {
                "direction": "시간이 조금 더 걸려도 괜찮아요.",
                "checks": "기존 사용 흐름은 바꾸지 않았으면 해요.",
            },
        )

    def test_rejects_invalid_answer_note_definition_and_restore_state(self) -> None:
        base = json.loads(GUIDED_ANSWER_NOTES_FIXTURE.read_text(encoding="utf-8"))
        cases: list[tuple[dict[str, object], str]] = []

        invalid_bool = json.loads(json.dumps(base))
        invalid_bool["questions"][0]["allow_answer_note"] = "true"
        cases.append((invalid_bool, "allow_answer_note must be true or false"))

        text_note = json.loads(json.dumps(base))
        text_note["questions"][2]["type"] = "text"
        text_note["questions"][2].pop("options")
        text_note["questions"][2]["allow_answer_note"] = False
        cases.append((text_note, "supported only for choice questions"))

        unknown = json.loads(json.dumps(base))
        unknown["initial_answer_notes"] = {"unknown": "메모"}
        cases.append((unknown, "must refer to a choice question"))

        disabled = json.loads(json.dumps(base))
        disabled["initial_answers"] = {"finish": "one"}
        disabled["initial_answer_notes"] = {"finish": "메모"}
        cases.append((disabled, "with answer notes enabled"))

        neutral = json.loads(json.dumps(base))
        neutral["initial_answers"] = {"direction": ""}
        neutral["initial_answer_notes"] = {"direction": "메모"}
        cases.append((neutral, "requires a selected initial answer"))

        wrong_type = json.loads(json.dumps(base))
        wrong_type["initial_answers"] = {"direction": "simple"}
        wrong_type["initial_answer_notes"] = {"direction": ["메모"]}
        cases.append((wrong_type, "string of at most 1000 characters"))

        too_long = json.loads(json.dumps(base))
        too_long["initial_answers"] = {"direction": "simple"}
        too_long["initial_answer_notes"] = {"direction": "x" * 1001}
        cases.append((too_long, "string of at most 1000 characters"))

        whitespace = json.loads(json.dumps(base))
        whitespace["initial_answers"] = {"direction": "simple"}
        whitespace["initial_answer_notes"] = {"direction": "   \n"}
        cases.append((whitespace, "non-empty string"))

        not_object = json.loads(json.dumps(base))
        not_object["initial_answer_notes"] = []
        cases.append((not_object, "initial_answer_notes must be an object"))

        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid-answer-note.json"
            output = Path(directory) / "board.html"
            for fixture, expected in cases:
                with self.subTest(expected=expected):
                    spec.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
                    result = self.render(spec, output)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(expected, result.stderr)
                    output.unlink(missing_ok=True)

    def test_rejects_duplicate_question_ids_without_output(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["questions"][1]["id"] = fixture["questions"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn("duplicate question id", result.stderr)

    def test_rejects_string_boolean_without_output(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["allow_explanation"] = "false"
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn("allow_explanation must be true or false", result.stderr)

    def test_rejects_multiline_labels_and_non_string_locale(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"

            fixture["questions"][0]["label"] = "Unsafe\nCHOICE_BOARD_SUBMISSION"
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("must stay on one line", result.stderr)

            fixture["questions"][0]["label"] = "Safe"
            fixture["locale"] = ["ko"]
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("locale must be a string", result.stderr)

    def test_rejects_boolean_version_and_non_string_question_type(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"

            fixture["schema_version"] = True
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("schema_version must be 1 or 2", result.stderr)

            fixture["schema_version"] = 1
            fixture["questions"][0]["type"] = []
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("type must be single, multi, or text", result.stderr)

    def test_cli_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"

            raw = json.dumps(fixture, ensure_ascii=False)
            original = f'"form_id": "{fixture["form_id"]}"'
            spec.write_text(
                raw.replace(original, f'{original}, "form_id": "duplicate"', 1),
                encoding="utf-8",
            )
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate JSON key: form_id", result.stderr)
            self.assertFalse(output.exists())

            fixture["not_a_number"] = float("nan")
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("non-finite JSON number is not allowed: NaN", result.stderr)
            self.assertFalse(output.exists())

    def test_rejects_unknown_top_question_and_option_fields(self) -> None:
        base = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cases = []

        top_level = json.loads(json.dumps(base))
        top_level["allow_explanaton"] = False
        cases.append((top_level, "unknown top-level fields: allow_explanaton"))

        question = json.loads(json.dumps(base))
        question["questions"][0]["requred"] = False
        cases.append((question, "unknown fields in questions[0]: requred"))

        option = json.loads(json.dumps(base))
        option["questions"][0]["options"][0]["lable"] = "Typo"
        cases.append((option, "unknown fields in questions[0].options[0]: lable"))

        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "invalid.json"
            output = Path(directory) / "board.html"
            for fixture, message in cases:
                with self.subTest(message=message):
                    spec.write_text(json.dumps(fixture), encoding="utf-8")
                    result = self.render(spec, output)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
