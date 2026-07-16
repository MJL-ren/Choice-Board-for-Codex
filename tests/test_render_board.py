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


class RenderBoardTests(unittest.TestCase):
    def render(self, spec: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--spec", str(spec), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )

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
        self.assertIn('inputs.forEach((input) => input.addEventListener("change", () => syncOtherVisibility(true)))', fragment)

        match = re.search(r'id="codex-choice-board-spec">([^<]+)</script>', fragment)
        self.assertIsNotNone(match)
        normalized = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
        self.assertTrue(normalized["allow_explanation"])
        self.assertTrue(normalized["questions"][0]["allow_other"])
        self.assertEqual(normalized["locale"], "ko")
        self.assertEqual(normalized["initial_answers"], {})
        self.assertEqual(normalized["initial_other_answers"], {})

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
            self.assertIn("schema_version must be 1", result.stderr)

            fixture["schema_version"] = 1
            fixture["questions"][0]["type"] = []
            spec.write_text(json.dumps(fixture), encoding="utf-8")
            result = self.render(spec, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("type must be single, multi, or text", result.stderr)


if __name__ == "__main__":
    unittest.main()
