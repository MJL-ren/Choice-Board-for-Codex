#!/usr/bin/env python3
"""Compile a concise internal Board Draft into the canonical public spec."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from render_board import SpecError, normalize_spec


TOP_FIELDS = {
    "draft_version",
    "mode",
    "form_id",
    "locale",
    "allow_explanation",
    "allow_deferred_explanation",
    "submit_label",
    "questions",
}
QUESTION_FIELDS = {
    "id",
    "type",
    "label",
    "description",
    "required",
    "allow_skip",
    "placeholder",
    "allow_other",
    "allow_answer_note",
    "options",
}


class DraftError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DraftError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise DraftError(f"non-finite JSON number is not allowed: {value}")


def load_json_strict(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except json.JSONDecodeError as exc:
        raise DraftError(f"invalid JSON: {exc}") from exc


def _reject_unknown_fields(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise DraftError(f"unknown {where} fields: {', '.join(unknown)}")


def expand_draft(raw: Any) -> dict[str, Any]:
    """Expand the internal syntax without applying the production size limit."""

    if not isinstance(raw, dict):
        raise DraftError("the Board Draft must be a JSON object")
    _reject_unknown_fields(raw, TOP_FIELDS, "Draft top-level")
    if type(raw.get("draft_version")) is not int or raw.get("draft_version") != 1:
        raise DraftError("draft_version must be 1")

    mode = raw.get("mode")
    if mode != "guided":
        raise DraftError('mode must be "guided"')
    if raw.get("locale") not in {"en", "ko"}:
        raise DraftError('locale must be "en" or "ko"')

    questions = raw.get("questions")
    if not isinstance(questions, list):
        raise DraftError("questions must be an array")
    if len(questions) < 4:
        raise DraftError(
            "guided Draft requires at least 4 questions; use canonical compact "
            "schema version 1 for 1 to 3 fixed questions"
        )

    compiled: dict[str, Any] = {
        "schema_version": 2,
        "presentation": "stepper",
    }
    for key in (
        "form_id",
        "locale",
        "allow_explanation",
        "allow_deferred_explanation",
        "submit_label",
    ):
        if key in raw:
            compiled[key] = raw[key]

    expanded_questions: list[dict[str, Any]] = []
    for index, item in enumerate(questions):
        where = f"questions[{index}]"
        if not isinstance(item, dict):
            raise DraftError(f"{where} must be an object")
        _reject_unknown_fields(item, QUESTION_FIELDS, where)
        for required_field in ("id", "type", "label"):
            if required_field not in item:
                raise DraftError(f"{where}.{required_field} is required")

        question_type = item.get("type")
        if question_type not in {"single", "multi", "text"}:
            raise DraftError(f"{where}.type must be single, multi, or text")
        expanded = {key: value for key, value in item.items() if key != "options"}
        if question_type == "text":
            if "options" in item:
                raise DraftError(f"{where}.options is not allowed for text")
            if "allow_other" in item:
                raise DraftError(f"{where}.allow_other is not allowed for text")
            if "allow_answer_note" in item:
                raise DraftError(f"{where}.allow_answer_note is not allowed for text")
        else:
            if "placeholder" in item:
                raise DraftError(f"{where}.placeholder is allowed only for text")
            pairs = item.get("options")
            if not isinstance(pairs, list):
                raise DraftError(f"{where}.options must be an array of pairs")
            expanded_options: list[dict[str, str]] = []
            for option_index, pair in enumerate(pairs):
                option_where = f"{where}.options[{option_index}]"
                if (
                    not isinstance(pair, list)
                    or len(pair) != 2
                    or not all(isinstance(value, str) for value in pair)
                ):
                    raise DraftError(f"{option_where} must be [value, label] strings")
                if pair[0] == "__other__":
                    raise DraftError("__other__ is reserved for the generated Other option")
                expanded_options.append({"value": pair[0], "label": pair[1]})
            expanded["options"] = expanded_options
        expanded_questions.append(expanded)

    compiled["questions"] = expanded_questions
    return compiled


def compile_draft(raw: Any) -> dict[str, Any]:
    """Return one normalized public spec for a fresh fixed-guided board."""

    try:
        return normalize_spec(expand_draft(raw))
    except SpecError as exc:
        raise DraftError(str(exc)) from exc


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, type=Path, help="Internal Board Draft JSON")
    parser.add_argument("--spec-output", required=True, type=Path, help="Canonical spec output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.draft.resolve() == args.spec_output.resolve():
            raise DraftError("Draft input and canonical output must be different files")
        compiled = compile_draft(load_json_strict(args.draft))
        spec_text = json.dumps(compiled, ensure_ascii=False, indent=2) + "\n"
        _atomic_write_text(args.spec_output, spec_text)
    except (OSError, DraftError) as exc:
        print(f"choice-board Draft compile failed: {exc}", file=sys.stderr)
        return 2

    option_count = sum(len(question.get("options", [])) for question in compiled["questions"])
    digest = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    print(
        "compiled choice board: "
        f"path={args.spec_output} sha256={digest} form_id={compiled['form_id']} "
        f"schema_version=2 presentation=stepper questions={len(compiled['questions'])} "
        f"options={option_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
