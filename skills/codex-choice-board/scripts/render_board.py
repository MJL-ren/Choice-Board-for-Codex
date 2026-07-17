#!/usr/bin/env python3
"""Validate a choice-board specification and render a Codex HTML fragment."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from branch_rules import (
        BranchRuleError,
        active_question_ids,
        branch_source_ids,
        normalize_branch_rules,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from branch_rules import (  # type: ignore[no-redef]
        BranchRuleError,
        active_question_ids,
        branch_source_ids,
        normalize_branch_rules,
    )


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SUBMISSION_ID_RE = re.compile(r"^cb-[A-Za-z0-9][A-Za-z0-9._-]{0,126}$")
FLOW_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
QUESTION_TYPES = {"single", "multi", "text"}
MAX_OPTIONS = 20
MAX_FRAGMENT_BYTES = 2_000_000
OTHER_VALUE = "__other__"
UI_COPY_KEYS = {
    "other",
    "otherPrompt",
    "answerNote",
    "answerNotePrompt",
    "answerNoteSummary",
    "needExplanation",
    "needExplanationGuided",
    "explanationLabel",
    "explanationPlaceholder",
    "sendAnswers",
    "sendExplanation",
    "deferExplanation",
    "sendAnswersAndExplanation",
    "pendingExplanation",
    "deferredHeading",
    "generalExplanation",
    "singleHint",
    "multiHint",
    "required",
    "requiredQuestionError",
    "otherQuestionError",
    "textTooLongError",
    "otherTooLongError",
    "answerNoteTooLongError",
    "explanationTooLongError",
    "sending",
    "sent",  # Deprecated input key retained for schema-v1 compatibility.
    "deliveryUnconfirmed",
    "retrySame",
    "changedAfterSend",
    "failed",
    "unavailable",
    "responseHeading",
    "explanationHeading",
    "draftHeading",
    "modelDataHeading",
    "modelDataHint",
    "back",
    "next",
    "skip",
    "progress",
    "branchProgress",
    "branchChanged",
    "reviewProgress",
    "reviewHeading",
    "reviewHint",
    "skipped",
}

GUIDED_TOP_LEVEL_BRANCH_FIELDS = {"branches", "branching", "branch_rules", "show_if"}
GUIDED_QUESTION_BRANCH_FIELDS = {"branches", "next", "next_if"}


class SpecError(ValueError):
    pass


def require_text(value: Any, field: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{field} must be a non-empty string")
    text = value.strip()
    if len(text) > maximum:
        raise SpecError(f"{field} must be at most {maximum} characters")
    return text


def optional_text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SpecError(f"{field} must be a string")
    if len(value) > maximum:
        raise SpecError(f"{field} must be at most {maximum} characters")
    return value


def require_single_line_text(value: Any, field: str, *, maximum: int = 500) -> str:
    text = require_text(value, field, maximum=maximum)
    if "\n" in text or "\r" in text:
        raise SpecError(f"{field} must stay on one line")
    return text


def optional_single_line_text(value: Any, field: str, *, maximum: int = 500) -> str:
    text = optional_text(value, field, maximum=maximum)
    if "\n" in text or "\r" in text:
        raise SpecError(f"{field} must stay on one line")
    return text


def optional_bool(value: Any, field: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise SpecError(f"{field} must be true or false")
    return value


def require_id(value: Any, field: str) -> str:
    text = require_text(value, field, maximum=64)
    if not ID_RE.fullmatch(text):
        raise SpecError(f"{field} must use ASCII letters, digits, dot, underscore, or hyphen")
    return text


def normalize_spec(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SpecError("the spec must be a JSON object")
    schema_version = raw.get("schema_version")
    if type(schema_version) is not int or schema_version not in {1, 2}:
        raise SpecError("schema_version must be 1 or 2")
    if schema_version == 1:
        if (
            "presentation" in raw
            or "initial_question_id" in raw
            or "initial_skipped_question_ids" in raw
            or "initial_deferred_explanation_requests" in raw
            or "allow_deferred_explanation" in raw
            or "flow_digest" in raw
        ):
            raise SpecError("schema_version 1 must omit guided-flow fields")
        forbidden = sorted(GUIDED_TOP_LEVEL_BRANCH_FIELDS.intersection(raw))
        if forbidden:
            raise SpecError(
                "schema_version 1 must omit branching fields: " + ", ".join(forbidden)
            )
        presentation = "compact"
    else:
        if raw.get("presentation") != "stepper":
            raise SpecError('schema_version 2 requires presentation "stepper"')
        forbidden = sorted(GUIDED_TOP_LEVEL_BRANCH_FIELDS.intersection(raw))
        if forbidden:
            raise SpecError(
                "top-level branching fields are not supported in schema_version 2; "
                "use question-level show_if: " + ", ".join(forbidden)
            )
        presentation = "stepper"

    form_id = require_id(raw.get("form_id"), "form_id")
    completion_parent_raw = raw.get("completion_parent")
    completion_parent: dict[str, str] | None = None
    if completion_parent_raw is not None:
        if not isinstance(completion_parent_raw, dict):
            raise SpecError("completion_parent must be an object")
        expected_completion_fields = {
            "parent_form_id",
            "parent_submission_id",
            "parent_flow_digest",
        }
        unknown_completion_fields = sorted(
            set(completion_parent_raw) - expected_completion_fields
        )
        missing_completion_fields = sorted(
            expected_completion_fields - set(completion_parent_raw)
        )
        if unknown_completion_fields:
            raise SpecError(
                "unknown completion_parent fields: "
                + ", ".join(unknown_completion_fields)
            )
        if missing_completion_fields:
            raise SpecError(
                "missing completion_parent fields: "
                + ", ".join(missing_completion_fields)
            )
        parent_form_id = require_id(
            completion_parent_raw.get("parent_form_id"),
            "completion_parent.parent_form_id",
        )
        parent_submission_id = completion_parent_raw.get("parent_submission_id")
        if not isinstance(parent_submission_id, str) or not SUBMISSION_ID_RE.fullmatch(
            parent_submission_id
        ):
            raise SpecError("completion_parent.parent_submission_id is invalid")
        parent_flow_digest = completion_parent_raw.get("parent_flow_digest")
        if not isinstance(parent_flow_digest, str) or not FLOW_DIGEST_RE.fullmatch(
            parent_flow_digest
        ):
            raise SpecError("completion_parent.parent_flow_digest is invalid")
        completion_parent = {
            "parent_form_id": parent_form_id,
            "parent_submission_id": parent_submission_id,
            "parent_flow_digest": parent_flow_digest,
        }
    locale = raw.get("locale", "en")
    if not isinstance(locale, str):
        raise SpecError("locale must be a string")
    if locale not in {"en", "ko"}:
        locale = "en"

    questions_raw = raw.get("questions")
    if not isinstance(questions_raw, list) or not questions_raw:
        raise SpecError("questions must contain at least 1 item")
    if schema_version == 1 and len(questions_raw) > 3:
        raise SpecError(
            "schema_version 1 compact boards support 1 to 3 questions; "
            "use schema_version 2 stepper for a longer fixed board"
        )

    seen_question_ids: set[str] = set()
    questions: list[dict[str, Any]] = []
    for index, item in enumerate(questions_raw):
        prefix = f"questions[{index}]"
        if not isinstance(item, dict):
            raise SpecError(f"{prefix} must be an object")
        if schema_version == 2:
            forbidden = sorted(GUIDED_QUESTION_BRANCH_FIELDS.intersection(item))
            if forbidden:
                raise SpecError(
                    f"unsupported branching fields in {prefix}; use show_if only: "
                    + ", ".join(forbidden)
                )
        else:
            forbidden = sorted(
                (GUIDED_QUESTION_BRANCH_FIELDS | {"show_if"}).intersection(item)
            )
            if forbidden:
                raise SpecError(
                    f"schema_version 1 must omit branching fields in {prefix}: "
                    + ", ".join(forbidden)
                )
            if "allow_skip" in item:
                raise SpecError(f"{prefix}.allow_skip is supported only in schema_version 2")
        question_id = require_id(item.get("id"), f"{prefix}.id")
        if question_id in seen_question_ids:
            raise SpecError(f"duplicate question id: {question_id}")
        seen_question_ids.add(question_id)

        question_type = item.get("type")
        if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
            raise SpecError(f"{prefix}.type must be single, multi, or text")

        question: dict[str, Any] = {
            "id": question_id,
            "type": question_type,
            "label": require_single_line_text(item.get("label"), f"{prefix}.label", maximum=240),
            "description": optional_text(item.get("description"), f"{prefix}.description", maximum=400),
            "required": optional_bool(item.get("required"), f"{prefix}.required", default=False),
        }
        if schema_version == 2:
            question["allow_skip"] = optional_bool(
                item.get("allow_skip"),
                f"{prefix}.allow_skip",
                default=True,
            )
            if "show_if" in item:
                question["show_if"] = item["show_if"]

        if question_type == "text":
            if "allow_answer_note" in item:
                raise SpecError(
                    f"{prefix}.allow_answer_note is supported only for choice questions"
                )
            question["placeholder"] = optional_text(item.get("placeholder"), f"{prefix}.placeholder", maximum=240)
        else:
            options_raw = item.get("options")
            if not isinstance(options_raw, list) or not 1 <= len(options_raw) <= MAX_OPTIONS:
                raise SpecError(f"{prefix}.options must contain 1 to {MAX_OPTIONS} items")
            seen_values: set[str] = set()
            options: list[dict[str, str]] = []
            for option_index, option_raw in enumerate(options_raw):
                option_prefix = f"{prefix}.options[{option_index}]"
                if not isinstance(option_raw, dict):
                    raise SpecError(f"{option_prefix} must be an object")
                value = require_id(option_raw.get("value"), f"{option_prefix}.value")
                if value == OTHER_VALUE:
                    raise SpecError(f"{OTHER_VALUE} is reserved for the Other option")
                if value in seen_values:
                    raise SpecError(f"duplicate option value in {question_id}: {value}")
                seen_values.add(value)
                options.append(
                    {
                        "value": value,
                        "label": require_single_line_text(
                            option_raw.get("label"),
                            f"{option_prefix}.label",
                            maximum=240,
                        ),
                    }
                )
            question["options"] = options
            question["allow_other"] = optional_bool(
                item.get("allow_other"),
                f"{prefix}.allow_other",
                default=True,
            )
            allow_answer_note = optional_bool(
                item.get("allow_answer_note"),
                f"{prefix}.allow_answer_note",
                default=False,
            )
            if allow_answer_note:
                question["allow_answer_note"] = True

        questions.append(question)

    branch_rules: dict[str, dict[str, Any]] = {}
    branch_sources: list[str] = []
    if schema_version == 2:
        try:
            branch_rules = normalize_branch_rules(questions)
            branch_sources = branch_source_ids(questions)
        except BranchRuleError as error:
            raise SpecError(str(error)) from error
        for question in questions:
            if question["id"] in branch_rules:
                question["show_if"] = branch_rules[question["id"]]

    if schema_version == 2 and completion_parent is not None:
        skippable_completion_ids = [
            question["id"] for question in questions if question["allow_skip"]
        ]
        if skippable_completion_ids:
            raise SpecError(
                "guided completion questions must set allow_skip false: "
                + ", ".join(skippable_completion_ids)
            )

    ui_copy_raw = raw.get("ui_copy", {})
    if not isinstance(ui_copy_raw, dict):
        raise SpecError("ui_copy must be an object")
    unknown_copy_keys = sorted(key for key in ui_copy_raw if key not in UI_COPY_KEYS)
    if unknown_copy_keys:
        raise SpecError(f"unknown ui_copy keys: {', '.join(unknown_copy_keys)}")
    ui_copy = {
        key: require_single_line_text(value, f"ui_copy.{key}", maximum=240)
        for key, value in ui_copy_raw.items()
    }
    allow_explanation = optional_bool(
        raw.get("allow_explanation"),
        "allow_explanation",
        default=True,
    )
    allow_deferred_explanation = True
    if schema_version == 2:
        allow_deferred_explanation = optional_bool(
            raw.get("allow_deferred_explanation"),
            "allow_deferred_explanation",
            default=True,
        )

    question_by_id = {question["id"]: question for question in questions}
    initial_answers_raw = raw.get("initial_answers", {})
    if not isinstance(initial_answers_raw, dict):
        raise SpecError("initial_answers must be an object")
    unknown_initial_ids = sorted(set(initial_answers_raw) - set(question_by_id))
    if unknown_initial_ids:
        raise SpecError(f"unknown initial answer question ids: {', '.join(unknown_initial_ids)}")

    initial_answers: dict[str, Any] = {}
    for question_id, value in initial_answers_raw.items():
        question = question_by_id[question_id]
        field = f"initial_answers.{question_id}"
        if question["type"] == "text":
            if not isinstance(value, str) or len(value) > 4000:
                raise SpecError(f"{field} must be a string of at most 4000 characters")
            initial_answers[question_id] = value
            continue

        allowed_values = [option["value"] for option in question["options"]]
        if question["allow_other"]:
            allowed_values.append(OTHER_VALUE)
        if question["type"] == "single":
            if not isinstance(value, str) or (value and value not in allowed_values):
                raise SpecError(f"{field} must be empty or a known option value")
            initial_answers[question_id] = value
            continue

        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise SpecError(f"{field} must be an array of known option values")
        if len(value) != len(set(value)) or any(item not in allowed_values for item in value):
            raise SpecError(f"{field} must contain unique known option values")
        selected = set(value)
        initial_answers[question_id] = [item for item in allowed_values if item in selected]

    initial_other_raw = raw.get("initial_other_answers", {})
    if not isinstance(initial_other_raw, dict):
        raise SpecError("initial_other_answers must be an object")
    initial_other_answers: dict[str, str] = {}
    for question_id, value in initial_other_raw.items():
        question = question_by_id.get(question_id)
        field = f"initial_other_answers.{question_id}"
        if not question or question["type"] == "text" or not question.get("allow_other"):
            raise SpecError(f"{field} must refer to a choice question with Other enabled")
        if not isinstance(value, str) or len(value) > 1000:
            raise SpecError(f"{field} must be a string of at most 1000 characters")
        selected = initial_answers.get(question_id, "" if question["type"] == "single" else [])
        has_other = selected == OTHER_VALUE if question["type"] == "single" else OTHER_VALUE in selected
        if not has_other:
            raise SpecError(f"{field} requires __other__ in initial_answers.{question_id}")
        initial_other_answers[question_id] = value

    initial_answer_notes_raw = raw.get("initial_answer_notes", {})
    if not isinstance(initial_answer_notes_raw, dict):
        raise SpecError("initial_answer_notes must be an object")
    initial_answer_notes: dict[str, str] = {}
    for question_id, value in initial_answer_notes_raw.items():
        question = question_by_id.get(question_id)
        field = f"initial_answer_notes.{question_id}"
        if (
            not question
            or question["type"] == "text"
            or not question.get("allow_answer_note")
        ):
            raise SpecError(f"{field} must refer to a choice question with answer notes enabled")
        if not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise SpecError(
                f"{field} must be a non-empty string of at most 1000 characters"
            )
        answer = initial_answers.get(
            question_id,
            "" if question["type"] == "single" else [],
        )
        if not answer:
            raise SpecError(f"{field} requires a selected initial answer")
        initial_answer_notes[question_id] = value

    initial_skipped_question_ids: list[str] = []
    if schema_version == 2:
        initial_skipped_raw = raw.get("initial_skipped_question_ids", [])
        if not isinstance(initial_skipped_raw, list) or any(
            not isinstance(item, str) for item in initial_skipped_raw
        ):
            raise SpecError("initial_skipped_question_ids must be an array of question ids")
        if len(initial_skipped_raw) != len(set(initial_skipped_raw)):
            raise SpecError("initial_skipped_question_ids must not contain duplicates")
        unknown_skipped_ids = sorted(set(initial_skipped_raw) - set(question_by_id))
        if unknown_skipped_ids:
            raise SpecError(
                f"unknown initial skipped question ids: {', '.join(unknown_skipped_ids)}"
            )
        initial_skipped_set = set(initial_skipped_raw)
        expected_skipped_question_ids = [
            question["id"] for question in questions if question["id"] in initial_skipped_set
        ]
        if initial_skipped_raw != expected_skipped_question_ids:
            raise SpecError("initial_skipped_question_ids must follow question order")
        initial_skipped_question_ids = expected_skipped_question_ids
        for question_id in initial_skipped_question_ids:
            question = question_by_id[question_id]
            if not question["allow_skip"]:
                raise SpecError(
                    f"initial_skipped_question_ids cannot include {question_id} because allow_skip is false"
                )
            answer = initial_answers.get(
                question_id,
                "" if question["type"] in {"single", "text"} else [],
            )
            has_answer = (
                bool(answer)
                if question["type"] == "multi"
                else answer not in {"", None}
            )
            if has_answer:
                raise SpecError(
                    f"initial skipped question {question_id} must have a neutral initial answer"
                )
            if question_id in initial_other_answers:
                raise SpecError(
                    f"initial skipped question {question_id} must not have an initial Other answer"
                )
            if question_id in initial_answer_notes:
                raise SpecError(
                    f"initial skipped question {question_id} must not have an initial answer note"
                )

    initial_deferred_explanation_requests: list[dict[str, str]] = []
    if schema_version == 2:
        initial_deferred_raw = raw.get("initial_deferred_explanation_requests", [])
        if not isinstance(initial_deferred_raw, list):
            raise SpecError("initial_deferred_explanation_requests must be an array")
        deferred_by_id: dict[str, str] = {}
        deferred_input_order: list[str] = []
        for index, item in enumerate(initial_deferred_raw):
            field = f"initial_deferred_explanation_requests[{index}]"
            if not isinstance(item, dict):
                raise SpecError(f"{field} must be an object")
            unknown_fields = sorted(set(item) - {"question_id", "request"})
            if unknown_fields:
                raise SpecError(f"unknown fields in {field}: {', '.join(unknown_fields)}")
            question_id = require_id(item.get("question_id"), f"{field}.question_id")
            if question_id not in question_by_id:
                raise SpecError(f"{field}.question_id must name a known question")
            if question_id in deferred_by_id:
                raise SpecError("initial_deferred_explanation_requests must not contain duplicates")
            request = optional_text(item.get("request"), f"{field}.request", maximum=2000)
            deferred_by_id[question_id] = request
            deferred_input_order.append(question_id)
        if deferred_by_id and not allow_explanation:
            raise SpecError("initial_deferred_explanation_requests require allow_explanation true")
        if deferred_by_id and not allow_deferred_explanation:
            raise SpecError(
                "initial_deferred_explanation_requests require allow_deferred_explanation true"
            )
        overlap = sorted(set(deferred_by_id) & set(initial_skipped_question_ids))
        if overlap:
            raise SpecError(
                "initial deferred and skipped question ids must not overlap: "
                + ", ".join(overlap)
            )
        expected_deferred_explanation_requests = [
            {"question_id": question["id"], "request": deferred_by_id[question["id"]]}
            for question in questions
            if question["id"] in deferred_by_id
        ]
        expected_deferred_order = [
            item["question_id"] for item in expected_deferred_explanation_requests
        ]
        if deferred_input_order != expected_deferred_order:
            raise SpecError(
                "initial_deferred_explanation_requests must follow question order"
            )
        initial_deferred_explanation_requests = expected_deferred_explanation_requests

    normalized = {
        "schema_version": schema_version,
        "form_id": form_id,
        "locale": locale,
        "allow_explanation": allow_explanation,
        "submit_label": optional_single_line_text(
            raw.get("submit_label"),
            "submit_label",
            maximum=80,
        ),
        "questions": questions,
        "ui_copy": ui_copy,
        "initial_answers": initial_answers,
        "initial_other_answers": initial_other_answers,
    }
    if "initial_answer_notes" in raw or initial_answer_notes:
        normalized["initial_answer_notes"] = initial_answer_notes
    if completion_parent is not None:
        normalized["completion_parent"] = completion_parent
    if schema_version == 2:
        initial_question_id = raw.get("initial_question_id", questions[0]["id"])
        initial_question_id = require_id(initial_question_id, "initial_question_id")
        if initial_question_id not in question_by_id:
            raise SpecError("initial_question_id must name a known question")

        if branch_rules:
            active_ids = active_question_ids(questions, initial_answers)
            hidden_ids = set(question_by_id) - set(active_ids)
            hidden_answer_ids = {
                question_id
                for question_id, value in initial_answers_raw.items()
                if question_id in hidden_ids and bool(value)
            }
            hidden_state_ids = (
                set(initial_other_raw)
                | set(initial_answer_notes_raw)
                | set(initial_skipped_question_ids)
                | {
                    item["question_id"]
                    for item in initial_deferred_explanation_requests
                }
            ) & hidden_ids
            invalid_hidden_ids = hidden_answer_ids | hidden_state_ids
            if invalid_hidden_ids:
                raise SpecError(
                    "restored state must keep hidden branch questions neutral: "
                    + ", ".join(
                        question["id"]
                        for question in questions
                        if question["id"] in invalid_hidden_ids
                    )
                )
            if initial_question_id in hidden_ids:
                raise SpecError("initial_question_id must name an active branch question")
            deferred_source_ids = set(branch_sources) & {
                item["question_id"]
                for item in initial_deferred_explanation_requests
            }
            if deferred_source_ids:
                raise SpecError(
                    "branch source questions cannot defer explanation: "
                    + ", ".join(
                        question["id"]
                        for question in questions
                        if question["id"] in deferred_source_ids
                    )
                )
        normalized["presentation"] = presentation
        normalized["initial_question_id"] = initial_question_id
        normalized["initial_skipped_question_ids"] = initial_skipped_question_ids
        normalized["initial_deferred_explanation_requests"] = (
            initial_deferred_explanation_requests
        )
        if "allow_deferred_explanation" in raw:
            normalized["allow_deferred_explanation"] = allow_deferred_explanation

        flow_definition = {
            key: value
            for key, value in normalized.items()
            if key
            not in {
                "initial_answers",
                "initial_other_answers",
                "initial_answer_notes",
                "initial_question_id",
                "initial_skipped_question_ids",
                "initial_deferred_explanation_requests",
            }
        }
        encoded_definition = json.dumps(
            flow_definition,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        flow_digest = f"sha256:{hashlib.sha256(encoded_definition).hexdigest()}"
        supplied_digest = raw.get("flow_digest")
        if supplied_digest is not None:
            if not isinstance(supplied_digest, str) or supplied_digest != flow_digest:
                raise SpecError("flow_digest does not match the normalized guided flow")
        normalized["flow_digest"] = flow_digest

    return normalized


def render_fragment(spec: dict[str, Any], template: str) -> str:
    marker = "__CHOICE_BOARD_SPEC_BASE64__"
    if template.count(marker) != 1:
        raise SpecError("template must contain exactly one spec marker")
    compact = json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(compact.encode("utf-8")).decode("ascii")
    fragment = template.replace(marker, encoded)
    if len(fragment.encode("utf-8")) >= MAX_FRAGMENT_BYTES:
        raise SpecError("rendered fragment must stay below 2 MB")
    return fragment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="Path to the input JSON specification")
    parser.add_argument("--output", required=True, type=Path, help="Path for the rendered HTML fragment")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "choice-board-template.html",
        help="Optional template override",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        normalized = normalize_spec(raw)
        template = args.template.read_text(encoding="utf-8")
        fragment = render_fragment(normalized, template)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(fragment, encoding="utf-8", newline="\n")
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        print(f"choice-board render failed: {exc}", file=sys.stderr)
        return 2
    print(f"rendered choice board: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
