#!/usr/bin/env python3
"""Validate a choice-board specification and render a Codex HTML fragment."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
QUESTION_TYPES = {"single", "multi", "text"}
MAX_QUESTIONS = 12
MAX_OPTIONS = 20
MAX_FRAGMENT_BYTES = 2_000_000
OTHER_VALUE = "__other__"
UI_COPY_KEYS = {
    "other",
    "otherPrompt",
    "needExplanation",
    "explanationLabel",
    "explanationPlaceholder",
    "sendAnswers",
    "sendExplanation",
    "singleHint",
    "multiHint",
    "required",
    "requiredQuestionError",
    "otherQuestionError",
    "textTooLongError",
    "otherTooLongError",
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
}


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
    if type(schema_version) is not int or schema_version != 1:
        raise SpecError("schema_version must be 1")

    form_id = require_id(raw.get("form_id"), "form_id")
    locale = raw.get("locale", "en")
    if not isinstance(locale, str):
        raise SpecError("locale must be a string")
    if locale not in {"en", "ko"}:
        locale = "en"

    questions_raw = raw.get("questions")
    if not isinstance(questions_raw, list) or not 1 <= len(questions_raw) <= MAX_QUESTIONS:
        raise SpecError(f"questions must contain 1 to {MAX_QUESTIONS} items")

    seen_question_ids: set[str] = set()
    questions: list[dict[str, Any]] = []
    for index, item in enumerate(questions_raw):
        prefix = f"questions[{index}]"
        if not isinstance(item, dict):
            raise SpecError(f"{prefix} must be an object")
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

        if question_type == "text":
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

        questions.append(question)

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

    return {
        "schema_version": 1,
        "form_id": form_id,
        "locale": locale,
        "allow_explanation": optional_bool(
            raw.get("allow_explanation"),
            "allow_explanation",
            default=True,
        ),
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
