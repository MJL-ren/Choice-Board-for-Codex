#!/usr/bin/env python3
"""Validate and evaluate the bounded one-layer Choice Board branch contract."""

from __future__ import annotations

from typing import Any


class BranchRuleError(ValueError):
    pass


def normalize_branch_rules(questions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return normalized rules keyed by target ID without mutating questions."""

    by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, question in enumerate(questions):
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id:
            raise BranchRuleError(f"questions[{index}].id must be a non-empty string")
        if question_id in by_id:
            raise BranchRuleError(f"duplicate question id: {question_id}")
        by_id[question_id] = (index, question)

    normalized: dict[str, dict[str, Any]] = {}
    for target_index, target in enumerate(questions):
        if "show_if" not in target:
            continue
        raw_rule = target["show_if"]
        target_id = target["id"]
        if not isinstance(raw_rule, dict):
            raise BranchRuleError(f"{target_id}.show_if must be an object")
        unknown = sorted(set(raw_rule) - {"question_id", "answer_in"})
        missing = sorted({"question_id", "answer_in"} - set(raw_rule))
        if unknown:
            raise BranchRuleError(
                f"unknown {target_id}.show_if fields: {', '.join(unknown)}"
            )
        if missing:
            raise BranchRuleError(
                f"missing {target_id}.show_if fields: {', '.join(missing)}"
            )

        source_id = raw_rule.get("question_id")
        if not isinstance(source_id, str) or source_id not in by_id:
            raise BranchRuleError(f"{target_id}.show_if.question_id must name a known question")
        source_index, source = by_id[source_id]
        if source_index >= target_index:
            raise BranchRuleError(f"{target_id}.show_if must reference an earlier question")
        if source.get("type") != "single":
            raise BranchRuleError(f"{target_id}.show_if source must be single-choice")
        if source.get("show_if") is not None:
            raise BranchRuleError(f"{target_id}.show_if source must be unconditional")

        answer_in = raw_rule.get("answer_in")
        if not isinstance(answer_in, list) or not answer_in:
            raise BranchRuleError(f"{target_id}.show_if.answer_in must be a non-empty array")
        if any(not isinstance(value, str) for value in answer_in):
            raise BranchRuleError(f"{target_id}.show_if.answer_in values must be strings")
        if len(answer_in) != len(set(answer_in)):
            raise BranchRuleError(f"{target_id}.show_if.answer_in must not contain duplicates")
        known_values = [
            option.get("value")
            for option in source.get("options", [])
            if isinstance(option, dict)
        ]
        if "__other__" in answer_in or any(value not in known_values for value in answer_in):
            raise BranchRuleError(
                f"{target_id}.show_if.answer_in must use known source option values"
            )
        normalized[target_id] = {
            "question_id": source_id,
            "answer_in": [value for value in known_values if value in set(answer_in)],
        }
    return normalized


def active_question_ids(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
) -> list[str]:
    """Evaluate the ordered active path for already validated one-layer rules."""

    rules = normalize_branch_rules(questions)
    active: list[str] = []
    for question in questions:
        question_id = question["id"]
        rule = rules.get(question_id)
        if rule is None or answers.get(rule["question_id"], "") in rule["answer_in"]:
            active.append(question_id)
    return active


def branch_source_ids(questions: list[dict[str, Any]]) -> list[str]:
    """Return source IDs in question order for deferred-explanation restrictions."""

    rules = normalize_branch_rules(questions)
    sources = {rule["question_id"] for rule in rules.values()}
    return [question["id"] for question in questions if question["id"] in sources]


def validate_returned_branch_state(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
    claimed_active_question_ids: Any,
    *,
    other_answers: dict[str, Any] | None = None,
    answer_notes: dict[str, Any] | None = None,
    skipped_question_ids: list[str] | None = None,
    deferred_explanation_requests: list[dict[str, Any]] | None = None,
    active_question_id: str | None = None,
) -> list[str]:
    """Recompute and validate the active path and every hidden-state invariant."""

    expected = active_question_ids(questions, answers)
    if not isinstance(claimed_active_question_ids, list) or any(
        not isinstance(question_id, str) for question_id in claimed_active_question_ids
    ):
        raise BranchRuleError("active_question_ids must be an array of question ids")
    if claimed_active_question_ids != expected:
        raise BranchRuleError("active_question_ids does not match the canonical branch path")

    question_by_id = {question["id"]: question for question in questions}
    hidden = set(question_by_id) - set(expected)
    invalid_hidden_answers = {
        question_id
        for question_id in hidden
        if bool(answers.get(question_id, ""))
    }
    other_answers = other_answers or {}
    answer_notes = answer_notes or {}
    skipped_question_ids = skipped_question_ids or []
    deferred_explanation_requests = deferred_explanation_requests or []
    invalid_hidden_state = (
        set(other_answers)
        | set(answer_notes)
        | set(skipped_question_ids)
        | {
            item.get("question_id")
            for item in deferred_explanation_requests
            if isinstance(item, dict)
        }
    ) & hidden
    invalid_hidden = invalid_hidden_answers | invalid_hidden_state
    if invalid_hidden:
        raise BranchRuleError("hidden branch questions must keep neutral returned state")
    if active_question_id is not None and active_question_id not in expected:
        raise BranchRuleError("active_question_id must belong to active_question_ids")
    return expected
