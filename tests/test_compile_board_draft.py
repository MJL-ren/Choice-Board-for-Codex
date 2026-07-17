from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "codex-choice-board"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from compile_board_draft import DraftError, compile_draft, load_json_strict  # noqa: E402
from render_board import normalize_spec, render_fragment  # noqa: E402


GUIDED_DRAFT = {
    "draft_version": 1,
    "mode": "guided",
    "form_id": "draft-guided-001",
    "locale": "ko",
    "questions": [
        {
            "id": "route",
            "type": "single",
            "label": "어떤 방향이 좋나요?",
            "required": True,
            "options": [["simple", "간단하게"], ["deep", "깊이 있게"]],
        },
        {
            "id": "note",
            "type": "text",
            "label": "덧붙일 내용이 있나요?",
            "placeholder": "없으면 건너뛰어도 돼요.",
        },
        {
            "id": "boundary",
            "type": "text",
            "label": "지켜야 할 경계가 있나요?",
        },
        {
            "id": "result",
            "type": "text",
            "label": "결과는 어떤 모양이면 좋나요?",
        },
    ],
}


def expanded_guided() -> dict[str, object]:
    return {
        "schema_version": 2,
        "presentation": "stepper",
        "form_id": "draft-guided-001",
        "locale": "ko",
        "questions": [
            {
                "id": "route",
                "type": "single",
                "label": "어떤 방향이 좋나요?",
                "required": True,
                "options": [
                    {"value": "simple", "label": "간단하게"},
                    {"value": "deep", "label": "깊이 있게"},
                ],
            },
            {
                "id": "note",
                "type": "text",
                "label": "덧붙일 내용이 있나요?",
                "placeholder": "없으면 건너뛰어도 돼요.",
            },
            {
                "id": "boundary",
                "type": "text",
                "label": "지켜야 할 경계가 있나요?",
            },
            {
                "id": "result",
                "type": "text",
                "label": "결과는 어떤 모양이면 좋나요?",
            },
        ],
    }


class BoardDraftTests(unittest.TestCase):
    def test_guided_draft_matches_public_spec_exactly(self) -> None:
        self.assertEqual(compile_draft(GUIDED_DRAFT), normalize_spec(expanded_guided()))

    def test_compact_draft_is_outside_the_internal_adapter(self) -> None:
        draft = copy.deepcopy(GUIDED_DRAFT)
        draft["mode"] = "compact"
        with self.assertRaisesRegex(DraftError, 'mode must be "guided"'):
            compile_draft(draft)

    def test_guided_draft_requires_four_questions(self) -> None:
        draft = copy.deepcopy(GUIDED_DRAFT)
        draft["questions"] = draft["questions"][:3]
        with self.assertRaisesRegex(DraftError, "at least 4 questions"):
            compile_draft(draft)

    def test_guided_draft_has_no_arbitrary_question_count_ceiling(self) -> None:
        draft = copy.deepcopy(GUIDED_DRAFT)
        for index in range(5, 31):
            draft["questions"].append(
                {
                    "id": f"detail_{index:02d}",
                    "type": "text",
                    "label": f"추가 확인 {index}",
                }
            )
        compiled = compile_draft(draft)
        self.assertEqual(len(compiled["questions"]), 30)

    def test_custom_or_missing_locale_is_outside_the_internal_adapter(self) -> None:
        for locale in (None, "fr"):
            with self.subTest(locale=locale):
                draft = copy.deepcopy(GUIDED_DRAFT)
                if locale is None:
                    draft.pop("locale")
                else:
                    draft["locale"] = locale
                with self.assertRaisesRegex(DraftError, "locale"):
                    compile_draft(draft)

    def test_draft_rejects_unknown_resume_and_branch_fields(self) -> None:
        for field, value in (
            ("initial_answers", {}),
            ("completion_parent", {}),
            ("flow_digest", "sha256:" + "0" * 64),
            ("ui_copy", {}),
            ("show_if", {"question_id": "route", "answer_in": ["simple"]}),
        ):
            with self.subTest(field=field):
                draft = copy.deepcopy(GUIDED_DRAFT)
                if field == "show_if":
                    draft["questions"][1][field] = value
                else:
                    draft[field] = value
                with self.assertRaisesRegex(DraftError, "unknown"):
                    compile_draft(draft)

    def test_draft_rejects_malformed_option_pairs(self) -> None:
        draft = copy.deepcopy(GUIDED_DRAFT)
        draft["questions"][0]["options"][0] = ["simple"]
        with self.assertRaisesRegex(DraftError, "\[value, label\]"):
            compile_draft(draft)

    def test_strict_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"draft_version":1,"draft_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(DraftError, "duplicate JSON key"):
                load_json_strict(path)

    def test_strict_loader_rejects_non_finite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.json"
            path.write_text('{"draft_version":1,"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(DraftError, "non-finite"):
                load_json_strict(path)

    def test_compiled_spec_renders_identically_to_public_spec(self) -> None:
        canonical = compile_draft(GUIDED_DRAFT)
        template = (SKILL_ROOT / "assets" / "choice-board-template.html").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            render_fragment(canonical, template),
            render_fragment(normalize_spec(expanded_guided()), template),
        )

    def test_answer_notes_are_explicit_opt_in_in_draft(self) -> None:
        baseline = compile_draft(GUIDED_DRAFT)
        self.assertNotIn("allow_answer_note", baseline["questions"][0])

        disabled = copy.deepcopy(GUIDED_DRAFT)
        disabled["questions"][0]["allow_answer_note"] = False
        self.assertEqual(compile_draft(disabled), baseline)

        enabled = copy.deepcopy(GUIDED_DRAFT)
        enabled["questions"][0]["allow_answer_note"] = True
        compiled = compile_draft(enabled)
        self.assertTrue(compiled["questions"][0]["allow_answer_note"])
        self.assertNotEqual(compiled["flow_digest"], baseline["flow_digest"])

        invalid_text = copy.deepcopy(GUIDED_DRAFT)
        invalid_text["questions"][1]["allow_answer_note"] = False
        with self.assertRaisesRegex(DraftError, "allow_answer_note is not allowed for text"):
            compile_draft(invalid_text)

    def test_cli_writes_canonical_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "draft.json"
            spec_path = root / "spec.json"
            draft_path.write_text(
                json.dumps(GUIDED_DRAFT, ensure_ascii=False),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "compile_board_draft.py"),
                    "--draft",
                    str(draft_path),
                    "--spec-output",
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            canonical = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertEqual(canonical, normalize_spec(expanded_guided()))
            first_bytes = spec_path.read_bytes()
            second = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "compile_board_draft.py"),
                    "--draft",
                    str(draft_path),
                    "--spec-output",
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_bytes, spec_path.read_bytes())

    def test_failed_cli_does_not_replace_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft_path = root / "draft.json"
            spec_path = root / "spec.json"
            draft_path.write_text('{"draft_version":1,"mode":"guided"}', encoding="utf-8")
            spec_path.write_text("keep-me\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "compile_board_draft.py"),
                    "--draft",
                    str(draft_path),
                    "--spec-output",
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(spec_path.read_text(encoding="utf-8"), "keep-me\n")


if __name__ == "__main__":
    unittest.main()
