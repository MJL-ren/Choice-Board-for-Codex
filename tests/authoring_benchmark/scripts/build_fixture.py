#!/usr/bin/env python3
"""Generate and verify locked benchmark fixture and golden canonical files."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchlib import (
    AUTHORITY_PATH,
    BENCH_ROOT,
    EXTRA_15Q_PATH,
    PRODUCTION_QUESTION_LIMIT,
    PROFILE_NAMES,
    RENDERER_PATH,
    SHARD_ALGORITHM_SHA256,
    SHARD_ALGORITHM_VERSION,
    TEMPLATE_PATH,
    BenchmarkError,
    atomic_write_text,
    canonical_json,
    file_sha256,
    load_json_strict,
    logical_questions,
    normalize_logical_spec,
    pretty_json,
    profile_paths,
    sha256_text,
)


def authority_for_profile(profile: str) -> dict[str, Any]:
    if profile not in PROFILE_NAMES:
        raise BenchmarkError(
            f"fixture profile must be one of: {', '.join(sorted(PROFILE_NAMES))}"
        )
    authority = load_json_strict(AUTHORITY_PATH)
    if not isinstance(authority, dict):
        raise BenchmarkError("fixture authority must be an object")
    questions = authority.get("questions")
    if not isinstance(questions, list) or len(questions) != 10:
        raise BenchmarkError("fixture authority must contain exactly 10 questions")

    result = deepcopy(authority)
    if profile == "q05":
        result["form_id"] = "authoring-benchmark-free-time-05q"
        result["questions"] = deepcopy(questions[:5])
    elif profile == "q15":
        extra = load_json_strict(EXTRA_15Q_PATH)
        if not isinstance(extra, list) or len(extra) != 5:
            raise BenchmarkError("15-question extension must contain exactly 5 questions")
        result["form_id"] = "authoring-benchmark-free-time-15q"
        result["questions"] = deepcopy(questions) + deepcopy(extra)
    return result


def fixture_markdown(
    authority: dict[str, Any], normalized: dict[str, Any], profile: str
) -> str:
    question_count = len(logical_questions(normalized))
    lines = [
        f"# Locked {question_count}-question fixture",
        "",
        "Copy the exact semantic content below into the assigned authoring format.",
        "Do not rewrite labels, descriptions, placeholders, IDs, option values,",
        "option labels, order, types, or flags.",
    ]
    if profile == "q15":
        lines.extend(
            [
                "",
                "## Benchmark-only 15-question boundary",
                "",
                "Author one logical input containing all 15 questions in one `questions` array.",
                "Do not split, chunk, or rename the form or questions while authoring.",
                "After authoring, the benchmark harness alone splits the logical input into",
                f"production-valid {PRODUCTION_QUESTION_LIMIT}+3 parts for normalization and rendering.",
                "This stress profile does not claim that one production Choice Board supports 15 questions.",
            ]
        )
    lines.extend(
        [
            "",
            "## Board",
            "",
            f"- form_id: `{authority['form_id']}`",
            f"- locale: `{authority.get('locale', 'en')}`",
            "- mode: fixed guided / one-question-at-a-time (`schema 2`, `stepper`)",
            "- explanation: enabled (current default)",
            "- explanation after completion: enabled (current default)",
            "- Skip: enabled on every question (current guided default)",
            "- Other: enabled on choice questions unless a question says `false`",
            "- Questions are optional unless a question says `required: true`",
            "",
            "Do not author derived `flow_digest` or any initial answer state.",
            "",
            "## Questions",
        ]
    )
    for index, question in enumerate(logical_questions(normalized), start=1):
        lines.extend(
            [
                "",
                f"### {index:02d}. `{question['id']}`",
                "",
                f"- type: `{question['type']}`",
                f"- label: {question['label']}",
                f"- required: `{str(question['required']).lower()}`",
                f"- allow_skip: `{str(question['allow_skip']).lower()}`",
            ]
        )
        if question["description"]:
            lines.append(f"- description: {question['description']}")
        if question["type"] == "text":
            if question["placeholder"]:
                lines.append(f"- placeholder: {question['placeholder']}")
        else:
            lines.append(f"- allow_other: `{str(question['allow_other']).lower()}`")
            lines.append("- options, in order:")
            for option in question["options"]:
                lines.append(f"  - `{option['value']}` — {option['label']}")
    return "\n".join(lines) + "\n"


def generate_outputs() -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for profile in sorted(PROFILE_NAMES):
        authority = authority_for_profile(profile)
        normalized = normalize_logical_spec(authority)
        questions = logical_questions(normalized)
        fixture = fixture_markdown(authority, normalized, profile)
        golden = pretty_json(normalized)
        question_counts = {kind: 0 for kind in ("single", "multi", "text")}
        option_count = 0
        for question in questions:
            question_counts[question["type"]] += 1
            option_count += len(question.get("options", []))

        if normalized.get("artifact_kind") == "benchmark_only_logical_bundle":
            part_counts = [len(part["questions"]) for part in normalized["parts"]]
            render_validation_mode = "chunked_production_boards_12_plus_3"
        else:
            part_counts = [len(questions)]
            render_validation_mode = "single_production_board"

        splitter_contract = {
            "version": SHARD_ALGORITHM_VERSION,
            "algorithm_sha256": SHARD_ALGORITHM_SHA256,
            "applied": len(part_counts) > 1,
            "logical_question_count": len(questions),
            "production_question_limit": PRODUCTION_QUESTION_LIMIT,
            "part_question_counts": part_counts,
            "split_stage": "after_authoring_before_production_normalization",
        }

        authority_text = pretty_json(authority)
        canonical_golden = canonical_json(normalized)
        manifest = {
            "manifest_version": 1,
            "fixture_profile": profile,
            "fixture_id": authority["form_id"],
            "generator_version": 2,
            "authority_sha256": file_sha256(AUTHORITY_PATH),
            "profile_authority_canonical_sha256": sha256_text(
                canonical_json(authority)
            ),
            "extra_questions_source_sha256": (
                file_sha256(EXTRA_15Q_PATH) if profile == "q15" else None
            ),
            "fixture_sha256": sha256_text(fixture),
            "golden_file_sha256": sha256_text(golden),
            "golden_canonical_sha256": sha256_text(canonical_golden),
            "renderer_sha256": file_sha256(RENDERER_PATH),
            "template_sha256": file_sha256(TEMPLATE_PATH),
            "authority_source_bytes": len(authority_text.encode("utf-8")),
            "fixture_source_bytes": len(fixture.encode("utf-8")),
            "golden_file_bytes": len(golden.encode("utf-8")),
            "golden_canonical_bytes": len(canonical_golden.encode("utf-8")),
            "question_count": len(questions),
            "question_type_counts": question_counts,
            "option_count": option_count,
            "render_validation_mode": render_validation_mode,
            "production_part_question_counts": part_counts,
            "logical_splitter_version": SHARD_ALGORITHM_VERSION,
            "logical_splitter_algorithm_sha256": SHARD_ALGORITHM_SHA256,
            "logical_splitter_contract_sha256": sha256_text(
                canonical_json(splitter_contract)
            ),
            "logical_splitter_contract": splitter_contract,
        }
        paths = profile_paths(profile)
        outputs[paths["fixture"]] = fixture
        outputs[paths["golden"]] = golden
        outputs[paths["manifest"]] = pretty_json(manifest)
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        atomic_write_text(path, content)


def check_outputs(outputs: dict[Path, str]) -> list[str]:
    problems: list[str] = []
    for path, expected in outputs.items():
        try:
            actual = path.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{path.relative_to(BENCH_ROOT)}: {exc}")
            continue
        if actual != expected:
            problems.append(f"{path.relative_to(BENCH_ROOT)}: generated content differs")
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = generate_outputs()
        if args.write:
            write_outputs(outputs)
            for path in outputs:
                print(path)
            return 0
        problems = check_outputs(outputs)
    except BenchmarkError as exc:
        print(f"error: {exc}")
        return 2
    if problems:
        for problem in problems:
            print(f"error: {problem}")
        return 2
    print("fixture artifacts are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
