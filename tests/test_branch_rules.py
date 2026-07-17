from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "codex-choice-board" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from branch_rules import (  # noqa: E402
    BranchRuleError,
    active_question_ids,
    branch_source_ids,
    normalize_branch_rules,
    validate_returned_branch_state,
)
from render_board import SpecError, normalize_spec  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-branch-candidate.json"
FIXED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided.json"


class BranchRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.questions = cls.spec["questions"]

    def test_candidate_rule_and_active_paths(self) -> None:
        self.assertEqual(
            normalize_branch_rules(self.questions),
            {"details": {"question_id": "depth", "answer_in": ["deep"]}},
        )
        self.assertEqual(branch_source_ids(self.questions), ["depth"])
        self.assertEqual(
            active_question_ids(self.questions, {"depth": ""}),
            ["depth", "note", "result"],
        )
        self.assertEqual(
            active_question_ids(self.questions, {"depth": "quick"}),
            ["depth", "note", "result"],
        )
        self.assertEqual(
            active_question_ids(self.questions, {"depth": "deep"}),
            ["depth", "details", "note", "result"],
        )

    def test_invalid_source_shapes_fail_closed(self) -> None:
        mutations = []
        unknown = copy.deepcopy(self.questions)
        unknown[1]["show_if"]["question_id"] = "missing"
        mutations.append((unknown, "known question"))
        forward = copy.deepcopy(self.questions)
        forward[1]["show_if"]["question_id"] = "result"
        mutations.append((forward, "earlier question"))
        non_single = copy.deepcopy(self.questions)
        non_single[3]["show_if"] = {"question_id": "details", "answer_in": ["cost"]}
        mutations.append((non_single, "single-choice"))
        nested = copy.deepcopy(self.questions)
        nested[1]["type"] = "single"
        nested[2]["show_if"] = {"question_id": "details", "answer_in": ["cost"]}
        mutations.append((nested, "unconditional"))
        for questions, message in mutations:
            with self.subTest(message=message):
                with self.assertRaisesRegex(BranchRuleError, message):
                    normalize_branch_rules(questions)

    def test_invalid_predicates_fail_closed(self) -> None:
        variants = []
        empty = copy.deepcopy(self.questions)
        empty[1]["show_if"]["answer_in"] = []
        variants.append((empty, "non-empty"))
        duplicate = copy.deepcopy(self.questions)
        duplicate[1]["show_if"]["answer_in"] = ["deep", "deep"]
        variants.append((duplicate, "duplicates"))
        unknown = copy.deepcopy(self.questions)
        unknown[1]["show_if"]["answer_in"] = ["unknown"]
        variants.append((unknown, "known source option"))
        other = copy.deepcopy(self.questions)
        other[1]["show_if"]["answer_in"] = ["__other__"]
        variants.append((other, "known source option"))
        extra = copy.deepcopy(self.questions)
        extra[1]["show_if"]["operator"] = "or"
        variants.append((extra, "unknown"))
        null_rule = copy.deepcopy(self.questions)
        null_rule[1]["show_if"] = None
        variants.append((null_rule, "must be an object"))
        for questions, message in variants:
            with self.subTest(message=message):
                with self.assertRaisesRegex(BranchRuleError, message):
                    normalize_branch_rules(questions)

    def test_answer_in_is_canonicalized_to_source_option_order(self) -> None:
        questions = copy.deepcopy(self.questions)
        questions[1]["show_if"]["answer_in"] = ["deep", "quick"]
        self.assertEqual(
            normalize_branch_rules(questions)["details"]["answer_in"],
            ["quick", "deep"],
        )

    def test_one_source_can_activate_multiple_sibling_targets(self) -> None:
        questions = copy.deepcopy(self.questions)
        questions.insert(
            2,
            {
                "id": "second_detail",
                "type": "text",
                "label": "추가 세부 내용",
                "show_if": {"question_id": "depth", "answer_in": ["deep"]},
            },
        )
        self.assertEqual(
            active_question_ids(questions, {"depth": "deep"}),
            ["depth", "details", "second_detail", "note", "result"],
        )

    def test_renderer_normalizes_candidate_and_preserves_rule_in_digest(self) -> None:
        normalized = normalize_spec(self.spec)
        self.assertEqual(
            normalized["questions"][1]["show_if"],
            {"question_id": "depth", "answer_in": ["deep"]},
        )
        self.assertRegex(normalized["flow_digest"], r"^sha256:[0-9a-f]{64}$")

        changed = copy.deepcopy(self.spec)
        changed["questions"][1]["show_if"]["answer_in"] = ["quick"]
        self.assertNotEqual(
            normalize_spec(changed)["flow_digest"],
            normalized["flow_digest"],
        )

    def test_fixed_guided_digest_did_not_change(self) -> None:
        fixed = json.loads(FIXED_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            normalize_spec(fixed)["flow_digest"],
            "sha256:67c5e21ecb1387d843304d19d824956b23cf49ff8c004e05b7a0bf3ae08f2d38",
        )

    def test_renderer_allows_only_neutral_hidden_answer_state(self) -> None:
        neutral = copy.deepcopy(self.spec)
        neutral["initial_answers"] = {"depth": "quick", "details": []}
        neutral["initial_question_id"] = "note"
        self.assertEqual(
            normalize_spec(neutral)["initial_answers"]["details"],
            [],
        )

        cases = []
        answered = copy.deepcopy(self.spec)
        answered["initial_answers"] = {"depth": "quick", "details": ["cost"]}
        cases.append(answered)

        other = copy.deepcopy(self.spec)
        other["initial_answers"] = {"depth": "quick", "details": ["__other__"]}
        other["initial_other_answers"] = {"details": "예산 안에서"}
        cases.append(other)

        note = copy.deepcopy(self.spec)
        note["initial_answers"] = {"depth": "quick", "details": ["cost"]}
        note["initial_answer_notes"] = {"details": "숨은 메모"}
        cases.append(note)

        skipped = copy.deepcopy(self.spec)
        skipped["initial_answers"] = {"depth": "quick", "details": []}
        skipped["initial_skipped_question_ids"] = ["details"]
        cases.append(skipped)

        deferred = copy.deepcopy(self.spec)
        deferred["initial_answers"] = {"depth": "quick", "details": []}
        deferred["initial_deferred_explanation_requests"] = [
            {"question_id": "details", "request": "설명"}
        ]
        cases.append(deferred)

        active_position = copy.deepcopy(self.spec)
        active_position["initial_answers"] = {"depth": "quick", "details": []}
        active_position["initial_question_id"] = "details"
        cases.append(active_position)

        for fixture in cases:
            with self.subTest(fixture=fixture):
                with self.assertRaisesRegex(
                    SpecError,
                    "hidden branch questions|active branch question",
                ):
                    normalize_spec(fixture)

    def test_branch_source_cannot_restore_deferred_explanation(self) -> None:
        fixture = copy.deepcopy(self.spec)
        fixture["initial_answers"] = {"depth": "deep"}
        fixture["initial_deferred_explanation_requests"] = [
            {"question_id": "depth", "request": "차이를 설명해 줘"}
        ]
        with self.assertRaisesRegex(SpecError, "branch source questions cannot defer"):
            normalize_spec(fixture)

    def test_receiver_recomputes_path_and_rejects_hidden_state(self) -> None:
        answers = {"depth": "quick", "details": [], "note": "", "result": "one"}
        self.assertEqual(
            validate_returned_branch_state(
                self.questions,
                answers,
                ["depth", "note", "result"],
                skipped_question_ids=["note"],
            ),
            ["depth", "note", "result"],
        )

        with self.assertRaisesRegex(BranchRuleError, "does not match"):
            validate_returned_branch_state(
                self.questions,
                answers,
                ["depth", "details", "note", "result"],
            )
        with self.assertRaisesRegex(BranchRuleError, "neutral returned state"):
            validate_returned_branch_state(
                self.questions,
                answers,
                ["depth", "note", "result"],
                answer_notes={"details": "숨은 메모"},
            )


if __name__ == "__main__":
    unittest.main()
