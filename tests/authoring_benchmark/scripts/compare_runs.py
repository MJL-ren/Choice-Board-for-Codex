#!/usr/bin/env python3
"""Compare one completed baseline run with one completed Draft run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from benchlib import (
    BenchmarkError,
    atomic_write_text,
    canonical_json,
    file_sha256,
    load_json_strict,
    sha256_bytes,
)


BUNDLE_MANIFEST_FILE = "RENDER_BUNDLE_MANIFEST.json"


def _ratio(draft: float, baseline: float) -> str:
    if baseline == 0:
        return "n/a"
    return f"{draft / baseline:.3f}x"


def _verify_bundle(
    run_dir: Path, state: dict[str, Any], canonical: dict[str, Any]
) -> tuple[dict[str, Any], list[bytes]]:
    result = state["result"]
    manifest_path = run_dir / BUNDLE_MANIFEST_FILE
    manifest = load_json_strict(manifest_path)
    if not isinstance(manifest, dict):
        raise BenchmarkError(f"render bundle manifest must be an object: {run_dir}")
    if file_sha256(manifest_path) != result.get("render_bundle_manifest_sha256"):
        raise BenchmarkError(f"render bundle manifest digest mismatch: {run_dir}")
    if manifest.get("render_bundle_manifest_version") != 1:
        raise BenchmarkError(f"unsupported render bundle manifest: {run_dir}")
    canonical_parts = canonical.get("parts")
    entries = manifest.get("parts")
    if not isinstance(canonical_parts, list) or not isinstance(entries, list):
        raise BenchmarkError(f"render bundle parts are missing: {run_dir}")
    if manifest.get("part_count") != len(entries) or len(entries) != len(canonical_parts):
        raise BenchmarkError(f"render bundle part count mismatch: {run_dir}")

    bodies: list[bytes] = []
    expected_start = 1
    for expected_index, (entry, canonical_part) in enumerate(
        zip(entries, canonical_parts), start=1
    ):
        if not isinstance(entry, dict) or not isinstance(canonical_part, dict):
            raise BenchmarkError(f"render bundle part must be an object: {run_dir}")
        filename = entry.get("file")
        expected_filename = f"BOARD_PART_{expected_index:02d}.html"
        if filename != expected_filename or Path(filename).name != filename:
            raise BenchmarkError(f"render bundle filename/order mismatch: {run_dir}")
        questions = canonical_part.get("questions")
        if not isinstance(questions, list):
            raise BenchmarkError(f"canonical bundle questions are missing: {run_dir}")
        question_count = len(questions)
        expected_end = expected_start + question_count - 1
        expected_entry = {
            "part_index": expected_index,
            "file": expected_filename,
            "form_id": canonical_part.get("form_id"),
            "question_start": expected_start,
            "question_end": expected_end,
            "question_count": question_count,
        }
        for key, value in expected_entry.items():
            if entry.get(key) != value:
                raise BenchmarkError(
                    f"render bundle {key} mismatch in part {expected_index}: {run_dir}"
                )
        body = (run_dir / filename).read_bytes()
        if entry.get("bytes") != len(body) or entry.get("sha256") != sha256_bytes(body):
            raise BenchmarkError(
                f"render bundle body evidence mismatch in part {expected_index}: {run_dir}"
            )
        bodies.append(body)
        expected_start = expected_end + 1

    aggregate = sha256_bytes(canonical_json(entries).encode("utf-8"))
    if manifest.get("aggregate_parts_sha256") != aggregate:
        raise BenchmarkError(f"render bundle aggregate digest mismatch: {run_dir}")
    if result.get("render_bundle_aggregate_sha256") != aggregate:
        raise BenchmarkError(f"run result aggregate digest mismatch: {run_dir}")
    if manifest.get("question_count") != expected_start - 1:
        raise BenchmarkError(f"render bundle question range mismatch: {run_dir}")
    return manifest, bodies


def _load_complete(run_dir: Path) -> dict[str, Any]:
    state = load_json_strict(run_dir / "RUN.json")
    if not isinstance(state, dict) or state.get("status") != "complete":
        raise BenchmarkError(f"run is not complete: {run_dir}")
    result = state.get("result")
    if not isinstance(result, dict):
        raise BenchmarkError(f"run result is missing: {run_dir}")
    canonical_path = run_dir / "CANONICAL.json"
    if file_sha256(canonical_path) != result.get("canonical_sha256"):
        raise BenchmarkError(f"canonical evidence digest mismatch: {run_dir}")
    canonical = load_json_strict(canonical_path)
    if not isinstance(canonical, dict):
        raise BenchmarkError(f"canonical evidence must be an object: {run_dir}")
    artifact_kind = result.get("render_artifact_kind", "single_board")
    if artifact_kind == "single_board":
        if file_sha256(run_dir / "BOARD.html") != result.get("board_sha256"):
            raise BenchmarkError(f"board evidence digest mismatch: {run_dir}")
    elif artifact_kind == "production_part_bundle":
        _verify_bundle(run_dir, state, canonical)
    else:
        raise BenchmarkError(f"unknown render artifact kind: {artifact_kind}")
    return state


def compare(run_a: Path, run_b: Path) -> str:
    states = [_load_complete(run_a), _load_complete(run_b)]
    by_mode = {state["mode"]: (state, run_dir) for state, run_dir in zip(states, (run_a, run_b))}
    if set(by_mode) != {"baseline_current_spec", "draft_compiled_spec"}:
        raise BenchmarkError("comparison requires one distinct baseline and one distinct Draft run")
    baseline, baseline_dir = by_mode["baseline_current_spec"]
    draft, draft_dir = by_mode["draft_compiled_spec"]
    if baseline["run_id"] == draft["run_id"] or baseline["thread_id"] == draft["thread_id"]:
        raise BenchmarkError("comparison requires distinct run and thread identities")
    baseline_profile = baseline.get("fixture_profile", "q10")
    draft_profile = draft.get("fixture_profile", "q10")
    if baseline_profile != draft_profile:
        raise BenchmarkError("comparison requires the same fixture profile")
    for key in (
        "question_count",
        "render_validation_mode",
        "production_part_question_counts",
    ):
        if baseline.get(key) != draft.get(key):
            raise BenchmarkError(f"scale metadata differs: {key}")

    shared_locks = {
        "fixture_sha256",
        "golden_file_sha256",
        "manifest_sha256",
        "renderer_sha256",
        "template_sha256",
        "benchlib_sha256",
        "runner_sha256",
        "compiler_sha256",
        "production_compiler_sha256",
    }
    for key in sorted(shared_locks):
        if baseline["locks"].get(key) != draft["locks"].get(key):
            raise BenchmarkError(f"run lock differs: {key}")
    if baseline["golden_canonical_sha256"] != draft["golden_canonical_sha256"]:
        raise BenchmarkError("golden canonical identity differs")

    baseline_canonical = (baseline_dir / "CANONICAL.json").read_bytes()
    draft_canonical = (draft_dir / "CANONICAL.json").read_bytes()
    if baseline_canonical != draft_canonical:
        raise BenchmarkError("canonical output bytes differ")
    artifact_kind = baseline["result"].get("render_artifact_kind", "single_board")
    if artifact_kind != draft["result"].get("render_artifact_kind", "single_board"):
        raise BenchmarkError("render artifact kinds differ")
    if artifact_kind == "single_board":
        baseline_board = (baseline_dir / "BOARD.html").read_bytes()
        draft_board = (draft_dir / "BOARD.html").read_bytes()
        if baseline_board != draft_board:
            raise BenchmarkError("rendered HTML bytes differ")
        rendered_equality_label = "single board bytes"
    else:
        baseline_manifest, baseline_parts = _verify_bundle(
            baseline_dir, baseline, load_json_strict(baseline_dir / "CANONICAL.json")
        )
        draft_manifest, draft_parts = _verify_bundle(
            draft_dir, draft, load_json_strict(draft_dir / "CANONICAL.json")
        )
        baseline_manifest_bytes = (baseline_dir / BUNDLE_MANIFEST_FILE).read_bytes()
        draft_manifest_bytes = (draft_dir / BUNDLE_MANIFEST_FILE).read_bytes()
        if baseline_manifest_bytes != draft_manifest_bytes:
            raise BenchmarkError("render bundle manifests differ")
        if baseline_parts != draft_parts:
            raise BenchmarkError("rendered production part bytes differ")
        rendered_equality_label = "ordered production part bytes"

    b = baseline["result"]
    d = draft["result"]
    dispatch_offset = abs(
        baseline["events"]["dispatch"]["perf_counter_ns"]
        - draft["events"]["dispatch"]["perf_counter_ns"]
    ) / 1_000_000
    lines = [
        "# Choice Board Authoring Benchmark Comparison",
        "",
        "- status: valid pilot pair",
        f"- baseline_run_id: {baseline['run_id']}",
        f"- draft_run_id: {draft['run_id']}",
        f"- fixture_profile: {baseline_profile}",
        f"- question_count: {baseline.get('question_count', 10)}",
        f"- render_validation_mode: {baseline.get('render_validation_mode', 'single_production_board')}",
        "- production_part_question_counts: "
        + ",".join(
            str(value)
            for value in baseline.get(
                "production_part_question_counts", [baseline.get("question_count", 10)]
            )
        ),
        "- normalized_canonical_equal: true",
        "- rendered_html_equal: true",
        f"- rendered_equality_scope: {rendered_equality_label}",
        f"- dispatch_offset_ms: {dispatch_offset:.3f}",
        "",
        "| Metric | Baseline current spec | Minimal Draft | Draft / Baseline |",
        "|---|---:|---:|---:|",
    ]
    rows = [
        ("Begin to first submit (ms)", "begin_to_first_submit_ms"),
        ("Begin to first valid canonical (ms)", "begin_to_valid_ms"),
        ("Dispatch to begin (ms)", "dispatch_to_begin_ms"),
        ("Authored file bytes", "authored_input_bytes"),
        ("Authored compact semantic bytes", "authored_semantic_bytes"),
        ("Compile/shape validation (ms)", "compile_ms"),
        ("Shard planning (ms)", "shard_plan_ms"),
        ("Production normalization (ms)", "normalize_ms"),
        ("Production render (ms)", "render_ms"),
    ]
    for label, key in rows:
        baseline_value = b.get(key, 0.0)
        draft_value = d.get(key, 0.0)
        lines.append(
            f"| {label} | {baseline_value} | {draft_value} | "
            f"{_ratio(draft_value, baseline_value)} |"
        )
    lines.extend(
        [
            "",
            f"- baseline_first_pass: {str(b['first_pass']).lower()} ({b['attempt_count']} attempt(s))",
            f"- draft_first_pass: {str(d['first_pass']).lower()} ({d['attempt_count']} attempt(s))",
            "",
            "This is a harness pilot, not an adoption verdict. Server/task wake-up latency is",
            "reported separately, and one pair cannot establish a stable authoring advantage.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-a", required=True, type=Path)
    parser.add_argument("--run-b", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = compare(args.run_a, args.run_b)
        if args.output:
            atomic_write_text(args.output, report)
    except (BenchmarkError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
