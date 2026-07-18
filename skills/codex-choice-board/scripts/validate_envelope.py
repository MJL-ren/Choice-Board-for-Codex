#!/usr/bin/env python3
"""Validate a returned Choice Board message against its canonical specification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from branch_rules import BranchRuleError, branch_source_ids, validate_returned_branch_state
    from render_board import OTHER_VALUE, SUBMISSION_ID_RE, SpecError, load_json_strict, normalize_spec
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from branch_rules import (  # type: ignore[no-redef]
        BranchRuleError,
        branch_source_ids,
        validate_returned_branch_state,
    )
    from render_board import (  # type: ignore[no-redef]
        OTHER_VALUE,
        SUBMISSION_ID_RE,
        SpecError,
        load_json_strict,
        normalize_spec,
    )


SUBMISSION_MARKER = "CHOICE_BOARD_SUBMISSION"
EXPLANATION_MARKER = "CHOICE_BOARD_EXPLANATION_REQUEST"
MARKER_KIND = {
    SUBMISSION_MARKER: "choice_board_submission",
    EXPLANATION_MARKER: "choice_board_explanation_request",
}
SUMMARY_COPY = {
    "en": {
        "other": "Other",
        "answerNoteSummary": "Note",
        "pendingExplanation": "Decide after explanation",
        "deferredHeading": "Questions that need explanation",
        "generalExplanation": "Explain the options generally",
        "responseHeading": "Choice Board response",
        "explanationHeading": "Choice Board explanation request",
        "draftHeading": "Current draft choices",
        "skipped": "Skipped",
    },
    "ko": {
        "other": "기타",
        "answerNoteSummary": "덧붙임",
        "pendingExplanation": "설명 후 결정",
        "deferredHeading": "설명이 필요한 항목",
        "generalExplanation": "선택지 전반 설명",
        "responseHeading": "선택 보드 답변",
        "explanationHeading": "선택 보드 설명 요청",
        "draftHeading": "현재 선택 초안",
        "skipped": "건너뜀",
    },
}


class EnvelopeError(ValueError):
    pass


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnvelopeError(f"{field} must be an object")
    return value


def _require_exact_fields(
    value: dict[str, Any],
    field: str,
    *,
    required: set[str],
    allowed: set[str],
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise EnvelopeError(f"unknown {field} fields: {', '.join(unknown)}")
    if missing:
        raise EnvelopeError(f"missing {field} fields: {', '.join(missing)}")


def _normalize_message_text(message: str) -> str:
    return message.replace("\r\n", "\n").replace("\r", "\n").strip()


def parse_returned_message(message: str) -> dict[str, Any]:
    """Return the last complete exact marker pair from a user message."""

    normalized = _normalize_message_text(message)
    lines = normalized.split("\n")
    last_error: Exception | None = None
    for index in range(len(lines) - 2, -1, -1):
        marker = lines[index]
        if marker not in MARKER_KIND or index + 1 >= len(lines):
            continue
        payload_line = lines[index + 1]
        if not payload_line:
            continue
        try:
            payload = load_json_strict(payload_line)
        except (json.JSONDecodeError, SpecError) as error:
            last_error = error
            continue
        if not isinstance(payload, dict):
            last_error = EnvelopeError("the marker payload must be a JSON object")
            continue
        return {
            "message": normalized,
            "marker": marker,
            "marker_index": index,
            "payload": payload,
            "payload_line": payload_line,
        }
    if last_error is not None:
        raise EnvelopeError(f"the last marker candidate has invalid JSON: {last_error}")
    raise EnvelopeError("no complete Choice Board marker and JSON pair was found")


def _neutral_answer(question: dict[str, Any]) -> Any:
    return [] if question["type"] == "multi" else ""


def _selected_other(question: dict[str, Any], answer: Any) -> bool:
    if question["type"] == "single":
        return answer == OTHER_VALUE
    if question["type"] == "multi":
        return OTHER_VALUE in answer
    return False


def _validate_answers(
    questions: list[dict[str, Any]],
    raw: Any,
    field: str,
) -> dict[str, Any]:
    answers = _require_object(raw, field)
    expected_ids = {question["id"] for question in questions}
    unknown = sorted(set(answers) - expected_ids)
    missing = [question["id"] for question in questions if question["id"] not in answers]
    if unknown:
        raise EnvelopeError(f"unknown {field} question ids: {', '.join(unknown)}")
    if missing:
        raise EnvelopeError(f"missing {field} question ids: {', '.join(missing)}")

    for question in questions:
        question_id = question["id"]
        answer = answers[question_id]
        answer_field = f"{field}.{question_id}"
        if question["type"] == "text":
            if not isinstance(answer, str) or len(answer) > 4000:
                raise EnvelopeError(f"{answer_field} must be a string of at most 4000 characters")
            continue

        allowed_values = [option["value"] for option in question["options"]]
        if question.get("allow_other"):
            allowed_values.append(OTHER_VALUE)
        if question["type"] == "single":
            if not isinstance(answer, str) or (answer and answer not in allowed_values):
                raise EnvelopeError(f"{answer_field} must be empty or a known option value")
            continue

        if not isinstance(answer, list) or any(not isinstance(item, str) for item in answer):
            raise EnvelopeError(f"{answer_field} must be an array of known option values")
        if len(answer) != len(set(answer)) or any(item not in allowed_values for item in answer):
            raise EnvelopeError(f"{answer_field} must contain unique known option values")
        canonical = [value for value in allowed_values if value in set(answer)]
        if answer != canonical:
            raise EnvelopeError(f"{answer_field} must follow canonical option order")
    return answers


def _validate_other_answers(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
    raw: Any,
    field: str,
) -> dict[str, str]:
    other_answers = _require_object(raw, field)
    expected_ids = {
        question["id"]
        for question in questions
        if _selected_other(question, answers[question["id"]])
    }
    unknown = sorted(set(other_answers) - expected_ids)
    missing = [question["id"] for question in questions if question["id"] in expected_ids and question["id"] not in other_answers]
    if unknown:
        raise EnvelopeError(f"unexpected {field} question ids: {', '.join(unknown)}")
    if missing:
        raise EnvelopeError(f"missing {field} question ids: {', '.join(missing)}")
    for question_id, value in other_answers.items():
        if not isinstance(value, str) or len(value) > 1000:
            raise EnvelopeError(f"{field}.{question_id} must be a string of at most 1000 characters")
    return other_answers


def _validate_ordered_ids(
    questions: list[dict[str, Any]],
    active_question_ids: list[str],
    raw: Any,
    field: str,
) -> list[str]:
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise EnvelopeError(f"{field} must be an array of question ids")
    if len(raw) != len(set(raw)):
        raise EnvelopeError(f"{field} must not contain duplicates")
    active = set(active_question_ids)
    unknown = sorted(set(raw) - active)
    if unknown:
        raise EnvelopeError(f"{field} contains inactive or unknown ids: {', '.join(unknown)}")
    expected = [question["id"] for question in questions if question["id"] in set(raw)]
    if raw != expected:
        raise EnvelopeError(f"{field} must follow question order")
    return raw


def _validate_answer_notes(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
    skipped: list[str],
    raw: Any,
    field: str,
) -> dict[str, str]:
    notes = _require_object(raw, field)
    question_by_id = {question["id"]: question for question in questions}
    for question_id, value in notes.items():
        question = question_by_id.get(question_id)
        if (
            question is None
            or question["type"] == "text"
            or not question.get("allow_answer_note")
        ):
            raise EnvelopeError(f"{field}.{question_id} must name a note-enabled choice question")
        if question_id in skipped or not answers[question_id]:
            raise EnvelopeError(f"{field}.{question_id} requires a real, non-skipped answer")
        if not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise EnvelopeError(
                f"{field}.{question_id} must be a non-empty string of at most 1000 characters"
            )
    return notes


def _validate_required_answers(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
    other_answers: dict[str, str],
    active_question_ids: list[str],
    skipped: list[str],
    deferred: list[str],
) -> None:
    active = set(active_question_ids)
    exempt = set(skipped) | set(deferred)
    for question in questions:
        question_id = question["id"]
        if question_id not in active or question_id in exempt:
            continue
        answer = answers[question_id]
        if question.get("required"):
            answered = bool(answer.strip()) if question["type"] == "text" else bool(answer)
            if not answered:
                raise EnvelopeError(f"required question {question_id} has no completed answer")
        if _selected_other(question, answer) and not other_answers[question_id].strip():
            raise EnvelopeError(f"other_answers.{question_id} must not be blank")


def _validate_deferred_requests(
    spec: dict[str, Any],
    active_question_ids: list[str],
    raw: Any,
) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise EnvelopeError("deferred_explanation_requests must be an array")
    active = set(active_question_ids)
    branch_sources = set(branch_source_ids(spec["questions"]))
    by_id: dict[str, str] = {}
    input_order: list[str] = []
    for index, item in enumerate(raw):
        field = f"deferred_explanation_requests[{index}]"
        item = _require_object(item, field)
        _require_exact_fields(
            item,
            field,
            required={"question_id", "request"},
            allowed={"question_id", "request"},
        )
        question_id = item["question_id"]
        request = item["request"]
        if not isinstance(question_id, str) or question_id not in active:
            raise EnvelopeError(f"{field}.question_id must name an active question")
        if question_id in by_id:
            raise EnvelopeError("deferred_explanation_requests must not contain duplicates")
        if question_id in branch_sources:
            raise EnvelopeError("branch source questions cannot defer explanation")
        if not isinstance(request, str) or len(request) > 2000:
            raise EnvelopeError(f"{field}.request must be a string of at most 2000 characters")
        by_id[question_id] = request
        input_order.append(question_id)
    expected_order = [
        question["id"] for question in spec["questions"] if question["id"] in by_id
    ]
    if input_order != expected_order:
        raise EnvelopeError("deferred_explanation_requests must follow question order")
    return [{"question_id": question_id, "request": by_id[question_id]} for question_id in input_order]


def _effective_copy(spec: dict[str, Any]) -> dict[str, str]:
    copy = dict(SUMMARY_COPY[spec["locale"] if spec["locale"] in SUMMARY_COPY else "en"])
    copy.update(spec.get("ui_copy", {}))
    return copy


def _readable_summary(
    spec: dict[str, Any],
    answers: dict[str, Any],
    other_answers: dict[str, str],
    answer_notes: dict[str, str],
    skipped: list[str],
    deferred: list[dict[str, str]],
    active_question_ids: list[str],
) -> str:
    copy = _effective_copy(spec)
    active = set(active_question_ids)
    skipped_set = set(skipped)
    deferred_set = {item["question_id"] for item in deferred}
    lines: list[str] = []
    for question in spec["questions"]:
        question_id = question["id"]
        if question_id not in active:
            continue
        if question_id in skipped_set:
            lines.append(f"- {question['label']}: {copy['skipped']}")
            continue
        answer = answers[question_id]
        if question["type"] == "multi":
            visible = ", ".join(
                _option_label(question, value, other_answers, copy) for value in answer
            ) or "—"
        elif question["type"] == "single":
            visible = _option_label(question, answer, other_answers, copy) if answer else "—"
        else:
            visible = answer or "—"
        if question_id in deferred_set:
            visible = (
                copy["pendingExplanation"]
                if visible == "—"
                else f"{visible} · {copy['pendingExplanation']}"
            )
        line = f"- {question['label']}: {visible}"
        note = answer_notes.get(question_id)
        if note:
            normalized_note = note.replace("\r\n", "\n").replace("\r", "\n")
            line += (
                f"\n  - {copy['answerNoteSummary']}: "
                + normalized_note.replace("\n", "\n    ")
            )
        lines.append(line)
    return "\n".join(lines)


def _option_label(
    question: dict[str, Any],
    value: str,
    other_answers: dict[str, str],
    copy: dict[str, str],
) -> str:
    if value == OTHER_VALUE:
        return f"{copy['other']}: {other_answers.get(question['id'], '')}"
    for option in question.get("options", []):
        if option["value"] == value:
            return option["label"]
    return value


def _validate_readable_summary(
    message: str,
    spec: dict[str, Any],
    payload: dict[str, Any],
    *,
    answers: dict[str, Any],
    other_answers: dict[str, str],
    answer_notes: dict[str, str],
    skipped: list[str],
    deferred: list[dict[str, str]],
    active_question_ids: list[str],
) -> None:
    copy = _effective_copy(spec)
    readable = _readable_summary(
        spec,
        answers,
        other_answers,
        answer_notes,
        skipped,
        deferred,
        active_question_ids,
    )
    if payload["kind"] == "choice_board_submission":
        heading = copy["responseHeading"]
        summary = readable
    else:
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
    expected_prefix = f"{heading}\n\n{summary}\n\n---"
    if not message.startswith(expected_prefix):
        raise EnvelopeError("the readable summary does not match the canonical payload")


def validate_payload(
    spec: dict[str, Any],
    marker: str,
    payload: dict[str, Any],
    message: str,
    *,
    allow_legacy_missing_submission_id: bool = False,
) -> dict[str, Any]:
    expected_kind = MARKER_KIND[marker]
    if payload.get("kind") != expected_kind:
        raise EnvelopeError("the marker and payload kind do not match")

    is_submission = expected_kind == "choice_board_submission"
    has_notes = any(question.get("allow_answer_note") for question in spec["questions"])
    has_branching = any(question.get("show_if") for question in spec["questions"])
    common = {"schema_version", "kind", "form_id", "submission_id"}
    required = {"schema_version", "kind", "form_id"}
    if not allow_legacy_missing_submission_id:
        required.add("submission_id")
    if is_submission:
        allowed = common | {"answers", "other_answers"}
        required |= {"answers", "other_answers"}
        answer_field = "answers"
        other_field = "other_answers"
        note_field = "answer_notes"
        skipped_field = "skipped_question_ids"
    else:
        if not spec.get("allow_explanation"):
            raise EnvelopeError("this board does not allow explanation requests")
        allowed = common | {"request", "draft_answers", "draft_other_answers"}
        required |= {"request", "draft_answers", "draft_other_answers"}
        answer_field = "draft_answers"
        other_field = "draft_other_answers"
        note_field = "draft_answer_notes"
        skipped_field = "draft_skipped_question_ids"
    if has_notes:
        allowed.add(note_field)
        required.add(note_field)
    if spec.get("completion_parent") is not None:
        allowed.add("completion_parent")
        required.add("completion_parent")
    if spec["schema_version"] == 2:
        allowed |= {"presentation", "flow_digest", skipped_field}
        required |= {"presentation", "flow_digest", skipped_field}
        if not is_submission:
            guided_explanation = {
                "explanation_mode",
                "deferred_explanation_requests",
                "active_question_id",
            }
            allowed |= guided_explanation
            required |= guided_explanation
        if has_branching:
            allowed.add("active_question_ids")
            required.add("active_question_ids")
    _require_exact_fields(payload, "payload", required=required, allowed=allowed)

    if (
        type(payload["schema_version"]) is not int
        or payload["schema_version"] != spec["schema_version"]
    ):
        raise EnvelopeError("schema_version does not match the canonical spec")
    if payload["form_id"] != spec["form_id"]:
        raise EnvelopeError("form_id does not match the canonical spec")
    submission_id = payload.get("submission_id")
    if submission_id is not None and (
        not isinstance(submission_id, str) or not SUBMISSION_ID_RE.fullmatch(submission_id)
    ):
        raise EnvelopeError("submission_id is invalid")
    if spec.get("completion_parent") is not None and payload["completion_parent"] != spec["completion_parent"]:
        raise EnvelopeError("completion_parent does not match the canonical spec")

    answers = _validate_answers(spec["questions"], payload[answer_field], answer_field)
    other_answers = _validate_other_answers(
        spec["questions"], answers, payload[other_field], other_field
    )

    if spec["schema_version"] == 2:
        if payload["presentation"] != "stepper":
            raise EnvelopeError('presentation must be "stepper"')
        if payload["flow_digest"] != spec["flow_digest"]:
            raise EnvelopeError("flow_digest does not match the canonical spec")
        if has_branching:
            claimed_active = payload["active_question_ids"]
            active_question_ids = validate_returned_branch_state(
                spec["questions"], answers, claimed_active
            )
        else:
            active_question_ids = [question["id"] for question in spec["questions"]]
        skipped = _validate_ordered_ids(
            spec["questions"], active_question_ids, payload[skipped_field], skipped_field
        )
        question_by_id = {question["id"]: question for question in spec["questions"]}
        for question_id in skipped:
            if not question_by_id[question_id].get("allow_skip"):
                raise EnvelopeError(f"{skipped_field} includes a question that cannot be skipped: {question_id}")
            if answers[question_id] != _neutral_answer(question_by_id[question_id]):
                raise EnvelopeError(f"skipped question {question_id} must keep its exact neutral answer")
    else:
        active_question_ids = [question["id"] for question in spec["questions"]]
        skipped = []

    answer_notes = (
        _validate_answer_notes(
            spec["questions"], answers, skipped, payload[note_field], note_field
        )
        if has_notes
        else {}
    )

    deferred: list[dict[str, str]] = []
    if is_submission:
        _validate_required_answers(
            spec["questions"],
            answers,
            other_answers,
            active_question_ids,
            skipped,
            [],
        )
    elif spec["schema_version"] == 1:
        request = payload["request"]
        if not isinstance(request, str) or len(request) > 2000:
            raise EnvelopeError("request must be a string of at most 2000 characters")
    else:
        request = payload["request"]
        if not isinstance(request, str) or len(request) > 2000:
            raise EnvelopeError("request must be a string of at most 2000 characters")
        mode = payload["explanation_mode"]
        if mode not in {"pause_now", "after_completion"}:
            raise EnvelopeError("explanation_mode must be pause_now or after_completion")
        deferred = _validate_deferred_requests(
            spec, active_question_ids, payload["deferred_explanation_requests"]
        )
        deferred_ids = [item["question_id"] for item in deferred]
        overlap = [question_id for question_id in skipped if question_id in set(deferred_ids)]
        if overlap:
            raise EnvelopeError(
                "skipped and deferred question ids must not overlap: " + ", ".join(overlap)
            )
        active_question_id = payload["active_question_id"]
        if not isinstance(active_question_id, str) or active_question_id not in active_question_ids:
            raise EnvelopeError("active_question_id must name an active question")
        if mode == "pause_now":
            if active_question_id in deferred_ids:
                raise EnvelopeError("pause_now active_question_id must not also be deferred")
        else:
            if request != "":
                raise EnvelopeError("after_completion request must be empty")
            if not deferred:
                raise EnvelopeError("after_completion requires at least one deferred question")
            if not spec.get("allow_deferred_explanation", True):
                raise EnvelopeError("this board does not allow deferred explanation")
            if active_question_id != deferred[0]["question_id"]:
                raise EnvelopeError("after_completion active_question_id must be the first deferred id")
            _validate_required_answers(
                spec["questions"],
                answers,
                other_answers,
                active_question_ids,
                skipped,
                deferred_ids,
            )

    if has_branching:
        validate_returned_branch_state(
            spec["questions"],
            answers,
            payload["active_question_ids"],
            other_answers=other_answers,
            answer_notes=answer_notes,
            skipped_question_ids=skipped,
            deferred_explanation_requests=deferred,
            active_question_id=(payload.get("active_question_id") if not is_submission else None),
        )

    for question_id in skipped:
        if question_id in other_answers or question_id in answer_notes:
            raise EnvelopeError(f"skipped question {question_id} must not have auxiliary state")

    _validate_readable_summary(
        message,
        spec,
        payload,
        answers=answers,
        other_answers=other_answers,
        answer_notes=answer_notes,
        skipped=skipped,
        deferred=deferred,
        active_question_ids=active_question_ids,
    )
    return {
        "kind": expected_kind,
        "form_id": spec["form_id"],
        "submission_id": submission_id,
        "active_question_ids": active_question_ids,
        "payload": payload,
    }


def validate_returned_message(
    raw_spec: Any,
    message: str,
    *,
    allow_legacy_missing_submission_id: bool = False,
) -> dict[str, Any]:
    spec = normalize_spec(raw_spec)
    parsed = parse_returned_message(message)
    result = validate_payload(
        spec,
        parsed["marker"],
        parsed["payload"],
        parsed["message"],
        allow_legacy_missing_submission_id=allow_legacy_missing_submission_id,
    )
    result.update(
        {
            "schema": "choice-board-envelope-validation.v1",
            "marker": parsed["marker"],
            "payload_line": parsed["payload_line"],
        }
    )
    return result


def compare_submission_reuse(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> bool:
    """Return True for an exact duplicate and fail on conflicting ID reuse."""

    submission_id = current.get("submission_id")
    if not submission_id or submission_id != previous.get("submission_id"):
        return False
    if current.get("payload_line") != previous.get("payload_line"):
        raise EnvelopeError("submission_id was reused with a different canonical payload")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="Canonical board JSON")
    parser.add_argument("--message", required=True, type=Path, help="Returned user message")
    parser.add_argument(
        "--previous-message",
        type=Path,
        help="Optional earlier returned message for duplicate/conflict checking",
    )
    parser.add_argument("--output", type=Path, help="Optional validated payload output JSON")
    parser.add_argument(
        "--allow-legacy-missing-submission-id",
        action="store_true",
        help="Explicitly accept a legacy envelope without duplicate protection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw_spec = load_json_strict(args.spec.read_text(encoding="utf-8"))
        result = validate_returned_message(
            raw_spec,
            args.message.read_text(encoding="utf-8"),
            allow_legacy_missing_submission_id=args.allow_legacy_missing_submission_id,
        )
        duplicate = False
        if args.previous_message is not None:
            previous = validate_returned_message(
                raw_spec,
                args.previous_message.read_text(encoding="utf-8"),
                allow_legacy_missing_submission_id=args.allow_legacy_missing_submission_id,
            )
            duplicate = compare_submission_reuse(result, previous)
        output = {
            key: value for key, value in result.items() if key != "payload_line"
        }
        output["duplicate"] = duplicate
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except (OSError, json.JSONDecodeError, SpecError, BranchRuleError, EnvelopeError) as error:
        print(f"choice-board envelope validation failed: {error}", file=sys.stderr)
        return 2
    suffix = " (exact duplicate)" if duplicate else ""
    print(
        f"validated choice-board envelope: {result['kind']} "
        f"{result['submission_id'] or 'legacy-no-id'}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
