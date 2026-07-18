from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "codex-choice-board" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from render_board import normalize_spec  # noqa: E402
from validate_envelope import (  # noqa: E402
    EnvelopeError,
    _effective_copy,
    _readable_summary,
    compare_submission_reuse,
    validate_returned_message,
)


COMPACT_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko.json"
BRANCH_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided-branch-candidate.json"
GUIDED_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-guided.json"
COMPLETION_FIXTURE = ROOT / "tests" / "fixtures" / "board-ko-completion.json"
VALIDATOR_SCRIPT = SCRIPTS / "validate_envelope.py"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def returned_message(raw_spec: dict[str, object], payload: dict[str, object]) -> str:
    spec = normalize_spec(raw_spec)
    copy = _effective_copy(spec)
    is_submission = payload["kind"] == "choice_board_submission"
    answers = payload["answers" if is_submission else "draft_answers"]
    other_answers = payload["other_answers" if is_submission else "draft_other_answers"]
    notes = payload.get("answer_notes" if is_submission else "draft_answer_notes", {})
    skipped = payload.get(
        "skipped_question_ids" if is_submission else "draft_skipped_question_ids",
        [],
    )
    deferred = payload.get("deferred_explanation_requests", [])
    active = payload.get(
        "active_question_ids",
        [question["id"] for question in spec["questions"]],
    )
    readable = _readable_summary(
        spec,
        answers,
        other_answers,
        notes,
        skipped,
        deferred,
        active,
    )
    if is_submission:
        marker = "CHOICE_BOARD_SUBMISSION"
        heading = copy["responseHeading"]
        summary = readable
    else:
        marker = "CHOICE_BOARD_EXPLANATION_REQUEST"
        heading = copy["explanationHeading"]
        if spec["schema_version"] == 2 and payload["explanation_mode"] == "after_completion":
            deferred_lines = "\n".join(
                f"- {next(question['label'] for question in spec['questions'] if question['id'] == item['question_id'])}: "
                f"{item['request'] or copy['generalExplanation']}"
                for item in deferred
            )
            summary = (
                f"{copy['deferredHeading']}\n{deferred_lines}\n\n"
                f"{copy['draftHeading']}\n{readable}"
            )
        else:
            summary = (
                f"{payload['request'] or copy['generalExplanation']}\n\n"
                f"{copy['draftHeading']}\n{readable}"
            )
    payload_line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        f"{heading}\n\n{summary}\n\n---\n\n"
        f"**Data for Codex**\n\nAutomatic data.\n\n```text\n"
        f"{marker}\n{payload_line}\n```"
    )


class EnvelopeValidationTests(unittest.TestCase):
    def compact_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "choice_board_submission",
            "form_id": "first-spike-ko",
            "answers": {
                "route": "handoff",
                "checks": ["scope", "evidence"],
                "note": "작게 확인해요.",
            },
            "other_answers": {},
            "submission_id": "cb-test-001",
        }

    def branch_payload(self) -> dict[str, object]:
        spec = normalize_spec(load(BRANCH_FIXTURE))
        return {
            "schema_version": 2,
            "kind": "choice_board_submission",
            "form_id": spec["form_id"],
            "answers": {
                "depth": "quick",
                "details": [],
                "note": "공통 메모",
                "result": "one",
            },
            "other_answers": {},
            "answer_notes": {},
            "skipped_question_ids": [],
            "presentation": "stepper",
            "flow_digest": spec["flow_digest"],
            "active_question_ids": ["depth", "note", "result"],
            "submission_id": "cb-branch-001",
        }

    def test_validates_complete_compact_message_and_summary(self) -> None:
        spec = load(COMPACT_FIXTURE)
        payload = self.compact_payload()
        result = validate_returned_message(spec, returned_message(spec, payload))
        self.assertEqual(result["kind"], "choice_board_submission")
        self.assertEqual(result["submission_id"], "cb-test-001")
        self.assertEqual(result["active_question_ids"], ["route", "checks", "note"])

    def test_summary_disagreement_fails_closed(self) -> None:
        spec = load(COMPACT_FIXTURE)
        payload = self.compact_payload()
        message = returned_message(spec, payload).replace(
            "이번 항목을 어떻게 처리할까요?: 담당 작업으로 전달",
            "이번 항목을 어떻게 처리할까요?: 지금 반영",
            1,
        )
        with self.assertRaisesRegex(EnvelopeError, "readable summary"):
            validate_returned_message(spec, message)

    def test_branch_requires_missing_hidden_key_and_exact_neutral_type(self) -> None:
        spec = load(BRANCH_FIXTURE)
        missing = self.branch_payload()
        missing["answers"] = dict(missing["answers"])
        del missing["answers"]["details"]
        with self.assertRaisesRegex(EnvelopeError, "missing answers question ids: details"):
            validate_returned_message(spec, returned_message(spec, missing))

        wrong_type = self.branch_payload()
        wrong_type["answers"] = dict(wrong_type["answers"], details="")
        with self.assertRaisesRegex(EnvelopeError, "answers.details must be an array"):
            validate_returned_message(spec, returned_message(spec, wrong_type))

    def test_branch_rejects_hidden_auxiliary_state_and_missing_note_map(self) -> None:
        spec = load(BRANCH_FIXTURE)
        hidden_note = self.branch_payload()
        hidden_note["answer_notes"] = {"details": "숨은 메모"}
        with self.assertRaisesRegex(EnvelopeError, "real, non-skipped answer"):
            validate_returned_message(spec, returned_message(spec, hidden_note))

        missing_note_map = self.branch_payload()
        del missing_note_map["answer_notes"]
        with self.assertRaisesRegex(EnvelopeError, "missing payload fields: answer_notes"):
            validate_returned_message(spec, returned_message(spec, missing_note_map))

    def test_rejects_unknown_payload_fields_and_wrong_flow_identity(self) -> None:
        spec = load(BRANCH_FIXTURE)
        unknown = self.branch_payload()
        unknown["active_questions"] = unknown["active_question_ids"]
        with self.assertRaisesRegex(EnvelopeError, "unknown payload fields: active_questions"):
            validate_returned_message(spec, returned_message(spec, unknown))

        wrong_digest = self.branch_payload()
        wrong_digest["flow_digest"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(EnvelopeError, "flow_digest"):
            validate_returned_message(spec, returned_message(spec, wrong_digest))

        boolean_version = self.branch_payload()
        boolean_version["schema_version"] = True
        with self.assertRaisesRegex(EnvelopeError, "schema_version"):
            validate_returned_message(spec, returned_message(spec, boolean_version))

    def test_rejects_duplicate_keys_in_returned_json(self) -> None:
        spec = load(COMPACT_FIXTURE)
        payload = self.compact_payload()
        message = returned_message(spec, payload)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        duplicate = line.replace(
            '"form_id":"first-spike-ko"',
            '"form_id":"first-spike-ko","form_id":"other"',
            1,
        )
        message = message.replace(line, duplicate, 1)
        with self.assertRaisesRegex(EnvelopeError, "duplicate JSON key: form_id"):
            validate_returned_message(spec, message)

    def test_validates_guided_after_completion_explanation(self) -> None:
        raw_spec = load(GUIDED_FIXTURE)
        spec = normalize_spec(raw_spec)
        payload = {
            "schema_version": 2,
            "kind": "choice_board_explanation_request",
            "form_id": spec["form_id"],
            "request": "",
            "draft_answers": {
                "route": "pilot",
                "checks": ["scope"],
                "tone": "",
                "note": "이 조건은 꼭 지켜 주세요.",
                "finish": "review",
            },
            "draft_other_answers": {},
            "draft_skipped_question_ids": [],
            "explanation_mode": "after_completion",
            "deferred_explanation_requests": [
                {"question_id": "tone", "request": "두 톤의 차이를 알려 줘"}
            ],
            "presentation": "stepper",
            "flow_digest": spec["flow_digest"],
            "active_question_id": "tone",
            "submission_id": "cb-guided-explain-001",
        }
        result = validate_returned_message(
            raw_spec,
            returned_message(raw_spec, payload),
        )
        self.assertEqual(result["kind"], "choice_board_explanation_request")

        payload["active_question_id"] = "finish"
        with self.assertRaisesRegex(EnvelopeError, "first deferred id"):
            validate_returned_message(raw_spec, returned_message(raw_spec, payload))

    def test_completion_parent_must_match_exactly(self) -> None:
        raw_spec = load(COMPLETION_FIXTURE)
        payload = {
            "schema_version": 1,
            "kind": "choice_board_submission",
            "form_id": raw_spec["form_id"],
            "answers": {"tone": "gentle"},
            "other_answers": {},
            "completion_parent": raw_spec["completion_parent"],
            "submission_id": "cb-completion-001",
        }
        validate_returned_message(raw_spec, returned_message(raw_spec, payload))

        payload["completion_parent"] = dict(payload["completion_parent"])
        payload["completion_parent"]["parent_submission_id"] = "cb-wrong"
        with self.assertRaisesRegex(EnvelopeError, "completion_parent"):
            validate_returned_message(raw_spec, returned_message(raw_spec, payload))

    def test_duplicate_and_conflicting_submission_id_reuse(self) -> None:
        spec = load(COMPACT_FIXTURE)
        payload = self.compact_payload()
        first = validate_returned_message(spec, returned_message(spec, payload))
        second = validate_returned_message(spec, returned_message(spec, payload))
        self.assertTrue(compare_submission_reuse(second, first))

        changed = self.compact_payload()
        changed["answers"] = dict(changed["answers"], route="apply")
        conflict = validate_returned_message(spec, returned_message(spec, changed))
        with self.assertRaisesRegex(EnvelopeError, "reused with a different"):
            compare_submission_reuse(conflict, first)

    def test_cli_validates_and_marks_an_exact_duplicate(self) -> None:
        spec = load(COMPACT_FIXTURE)
        message = returned_message(spec, self.compact_payload())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec_path = root / "canonical.json"
            message_path = root / "returned.md"
            output_path = root / "validated.json"
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False),
                encoding="utf-8",
            )
            message_path.write_text(message, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_SCRIPT),
                    "--spec",
                    str(spec_path),
                    "--message",
                    str(message_path),
                    "--previous-message",
                    str(message_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            validated = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertTrue(validated["duplicate"])
        self.assertEqual(validated["submission_id"], "cb-test-001")


if __name__ == "__main__":
    unittest.main()
