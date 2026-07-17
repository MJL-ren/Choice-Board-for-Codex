#!/usr/bin/env python3
"""Prepare, time, validate, and finalize one authoring benchmark run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchlib import (
    BENCH_ROOT,
    PROFILE_NAMES,
    PRODUCTION_QUESTION_LIMIT,
    RENDERER_PATH,
    TEMPLATE_PATH,
    BenchmarkError,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    canonical_json,
    difference_paths,
    file_sha256,
    load_json_strict,
    loads_json_strict,
    normalize_logical_spec,
    normalized_parts,
    profile_paths,
    render_logical_parts,
    require_exact_keys,
    sha256_bytes,
)
from compile_draft import compile_draft


RUN_FILE = "RUN.json"
AUTHORED_FILE = "AUTHORED_INPUT.json"
COMPILED_FILE = "COMPILED_INPUT.json"
CANONICAL_FILE = "CANONICAL.json"
BOARD_FILE = "BOARD.html"
BUNDLE_MANIFEST_FILE = "RENDER_BUNDLE_MANIFEST.json"
CALLBACK_FILE = "CALLBACK.md"
MAX_ATTEMPTS = 2
MODES = {"baseline_current_spec", "draft_compiled_spec"}

BASELINE_TOP_FIELDS = {
    "schema_version",
    "presentation",
    "form_id",
    "locale",
    "allow_explanation",
    "allow_deferred_explanation",
    "submit_label",
    "questions",
}
BASELINE_QUESTION_FIELDS = {
    "id",
    "type",
    "label",
    "description",
    "required",
    "allow_skip",
    "placeholder",
    "allow_other",
    "options",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def contract_path(mode: str) -> Path:
    if mode == "baseline_current_spec":
        return BENCH_ROOT / "BASELINE_CONTRACT.md"
    if mode == "draft_compiled_spec":
        return BENCH_ROOT / "DRAFT_CONTRACT.md"
    raise BenchmarkError(f"unknown benchmark mode: {mode}")


def git_snapshot() -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=BENCH_ROOT.parents[1],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise BenchmarkError(result.stderr.strip() or "git command failed")
        return result.stdout.strip()

    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain=v1", "--untracked-files=all")
    encoded = status.encode("utf-8")
    return {
        "head": head,
        "dirty": bool(status),
        "status_entry_count": len(status.splitlines()) if status else 0,
        "status_sha256": sha256_bytes(encoded),
    }


def current_locks(mode: str, fixture_profile: str = "q10") -> dict[str, str]:
    paths = profile_paths(fixture_profile)
    production_compiler = (
        BENCH_ROOT.parents[1]
        / "skills"
        / "codex-choice-board"
        / "scripts"
        / "compile_board_draft.py"
    )
    return {
        "fixture_sha256": file_sha256(paths["fixture"]),
        "golden_file_sha256": file_sha256(paths["golden"]),
        "manifest_sha256": file_sha256(paths["manifest"]),
        "renderer_sha256": file_sha256(RENDERER_PATH),
        "template_sha256": file_sha256(TEMPLATE_PATH),
        "contract_sha256": file_sha256(contract_path(mode)),
        "benchlib_sha256": file_sha256(Path(__file__).with_name("benchlib.py")),
        "runner_sha256": file_sha256(Path(__file__)),
        "compiler_sha256": file_sha256(Path(__file__).with_name("compile_draft.py")),
        "production_compiler_sha256": file_sha256(production_compiler),
    }


def verify_fixture_manifest(fixture_profile: str = "q10") -> dict[str, Any]:
    paths = profile_paths(fixture_profile)
    manifest = load_json_strict(paths["manifest"])
    if not isinstance(manifest, dict):
        raise BenchmarkError("benchmark manifest must be an object")
    expected = {
        "fixture_sha256": file_sha256(paths["fixture"]),
        "golden_file_sha256": file_sha256(paths["golden"]),
        "renderer_sha256": file_sha256(RENDERER_PATH),
        "template_sha256": file_sha256(TEMPLATE_PATH),
    }
    for key, actual in expected.items():
        if manifest.get(key) != actual:
            raise BenchmarkError(
                f"{key} does not match {paths['manifest'].name}; "
                "run build_fixture.py --write"
            )
    if manifest.get("fixture_profile", fixture_profile) != fixture_profile:
        raise BenchmarkError("fixture profile does not match manifest")
    golden = load_json_strict(paths["golden"])
    digest = sha256_bytes(canonical_json(golden).encode("utf-8"))
    if manifest.get("golden_canonical_sha256") != digest:
        raise BenchmarkError("golden canonical digest does not match manifest")
    return manifest


def load_state(run_dir: Path) -> dict[str, Any]:
    state = load_json_strict(run_dir / RUN_FILE)
    if not isinstance(state, dict):
        raise BenchmarkError("RUN.json must be an object")
    return state


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    atomic_write_json(run_dir / RUN_FILE, state)


def prepare_run(
    run_dir: Path,
    *,
    run_id: str,
    mode: str,
    thread_id: str,
    source_thread_id: str,
    fixture_profile: str = "q10",
) -> dict[str, Any]:
    if mode not in MODES:
        raise BenchmarkError(f"mode must be one of: {', '.join(sorted(MODES))}")
    manifest = verify_fixture_manifest(fixture_profile)
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / RUN_FILE
    identity = {
        "run_id": run_id,
        "mode": mode,
        "thread_id": thread_id,
        "source_thread_id": source_thread_id,
        "fixture_profile": fixture_profile,
    }
    if state_path.exists():
        state = load_state(run_dir)
        if any(state.get(key) != value for key, value in identity.items()):
            raise BenchmarkError("run directory already belongs to a different run")
        return state

    state: dict[str, Any] = {
        "run_schema_version": 1,
        **identity,
        "status": "prepared",
        "prepared_at": utc_now(),
        "python_version": sys.version.split()[0],
        "fixture_id": manifest["fixture_id"],
        "question_count": manifest["question_count"],
        "render_validation_mode": manifest["render_validation_mode"],
        "production_part_question_counts": manifest[
            "production_part_question_counts"
        ],
        "golden_canonical_sha256": manifest["golden_canonical_sha256"],
        "locks": current_locks(mode, fixture_profile),
        "git": git_snapshot(),
        "events": {"dispatch": None, "begin": None},
        "attempt_limit": MAX_ATTEMPTS,
        "attempts": [],
        "result": None,
    }
    save_state(run_dir, state)
    return state


def mark_event(run_dir: Path, kind: str, event_id: str) -> dict[str, Any]:
    if kind not in {"dispatch", "begin"}:
        raise BenchmarkError("event kind must be dispatch or begin")
    state = load_state(run_dir)
    existing = state["events"].get(kind)
    if existing is not None:
        if existing.get("event_id") != event_id:
            raise BenchmarkError(f"{kind} already recorded with a different event id")
        return state
    if kind == "dispatch" and state["status"] != "prepared":
        raise BenchmarkError("dispatch requires prepared status")
    if kind == "begin" and state["status"] != "dispatched":
        raise BenchmarkError("begin requires dispatched status")
    state["events"][kind] = {
        "event_id": event_id,
        "utc": utc_now(),
        "perf_counter_ns": time.perf_counter_ns(),
    }
    state["status"] = "dispatched" if kind == "dispatch" else "started"
    save_state(run_dir, state)
    return state


def verify_run_locks(state: dict[str, Any]) -> None:
    actual = current_locks(state["mode"], state.get("fixture_profile", "q10"))
    for key, expected in state["locks"].items():
        if actual.get(key) != expected:
            raise BenchmarkError(f"locked benchmark file changed during run: {key}")


def validate_baseline(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise BenchmarkError("the baseline spec must be a JSON object")
    require_exact_keys(raw, BASELINE_TOP_FIELDS, "baseline top-level")
    if type(raw.get("schema_version")) is not int or raw.get("schema_version") != 2:
        raise BenchmarkError("baseline schema_version must be 2")
    if raw.get("presentation") != "stepper":
        raise BenchmarkError('baseline presentation must be "stepper"')
    for key in ("form_id", "locale", "questions"):
        if key not in raw:
            raise BenchmarkError(f"baseline {key} is required")
    questions = raw.get("questions")
    if not isinstance(questions, list):
        raise BenchmarkError("baseline questions must be an array")
    for index, question in enumerate(questions):
        label = f"questions[{index}]"
        if not isinstance(question, dict):
            raise BenchmarkError(f"{label} must be an object")
        require_exact_keys(question, BASELINE_QUESTION_FIELDS, label)
        question_type = question.get("type")
        if question_type not in {"single", "multi", "text"}:
            raise BenchmarkError(f"{label}.type must be single, multi, or text")
        for required_key in ("id", "type", "label"):
            if required_key not in question:
                raise BenchmarkError(f"{label}.{required_key} is required")
        if question_type == "text":
            if "options" in question or "allow_other" in question:
                raise BenchmarkError(f"{label} has choice-only fields")
        else:
            if "placeholder" in question:
                raise BenchmarkError(f"{label}.placeholder is allowed only for text")
            options = question.get("options")
            if not isinstance(options, list):
                raise BenchmarkError(f"{label}.options must be an array")
            for option_index, option in enumerate(options):
                option_label = f"{label}.options[{option_index}]"
                if not isinstance(option, dict):
                    raise BenchmarkError(f"{option_label} must be an object")
                require_exact_keys(option, {"value", "label"}, option_label)
                if set(option) != {"value", "label"}:
                    raise BenchmarkError(f"{option_label} requires value and label")
                if option.get("value") == "__other__":
                    raise BenchmarkError(
                        "__other__ is reserved for the generated Other option"
                    )
    return raw


def _elapsed_ms(start_ns: int, end_ns: int) -> float:
    return round((end_ns - start_ns) / 1_000_000, 3)


def _render_bundle(
    normalized: dict[str, Any],
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Render each production-sized part and build deterministic bundle evidence."""
    if normalized.get("artifact_kind") != "benchmark_only_logical_bundle":
        raise BenchmarkError("render bundle requires benchmark-only logical bundle")
    parts = normalized_parts(normalized)
    rendered_html = render_logical_parts(normalized)
    if len(parts) != len(rendered_html):
        raise BenchmarkError("rendered part count differs from normalized part count")

    rendered: list[tuple[str, bytes]] = []
    entries: list[dict[str, Any]] = []
    question_start = 1
    for part_index, (part, html) in enumerate(zip(parts, rendered_html), start=1):
        if not isinstance(part, dict):
            raise BenchmarkError(f"render bundle part {part_index} must be an object")
        questions = part.get("questions")
        if not isinstance(questions, list) or not questions:
            raise BenchmarkError(
                f"render bundle part {part_index} questions must be non-empty"
            )
        filename = f"BOARD_PART_{part_index:02d}.html"
        body = html.encode("utf-8")
        question_count = len(questions)
        question_end = question_start + question_count - 1
        rendered.append((filename, body))
        entries.append(
            {
                "part_index": part_index,
                "file": filename,
                "form_id": part.get("form_id"),
                "question_start": question_start,
                "question_end": question_end,
                "question_count": question_count,
                "bytes": len(body),
                "sha256": sha256_bytes(body),
            }
        )
        question_start = question_end + 1

    aggregate = sha256_bytes(canonical_json(entries).encode("utf-8"))
    manifest = {
        "render_bundle_manifest_version": 1,
        "artifact_kind": "production_part_render_bundle",
        "logical_form_id": normalized.get("logical_form_id"),
        "question_count": normalized.get("question_count"),
        "production_question_limit": normalized.get("production_question_limit"),
        "canonical_logical_sha256": sha256_bytes(
            canonical_json(normalized).encode("utf-8")
        ),
        "part_count": len(entries),
        "parts": entries,
        "aggregate_parts_sha256": aggregate,
    }
    return rendered, manifest


def _callback_markdown(state: dict[str, Any]) -> str:
    result = state["result"]
    lines = [
            "# Choice Board Authoring Benchmark Callback",
            "",
            f"- run_id: {state['run_id']}",
            f"- mode: {state['mode']}",
            f"- fixture_profile: {state.get('fixture_profile', 'q10')}",
            f"- question_count: {state['question_count']}",
            f"- render_validation_mode: {state['render_validation_mode']}",
            "- production_part_question_counts: "
            + ",".join(str(value) for value in state["production_part_question_counts"]),
            f"- status: {state['status']}",
            f"- thread_id: {state['thread_id']}",
            f"- first_pass: {str(result['first_pass']).lower()}",
            f"- attempts: {result['attempt_count']}",
            f"- dispatch_to_begin_ms: {result['dispatch_to_begin_ms']}",
            f"- begin_to_first_submit_ms: {result['begin_to_first_submit_ms']}",
            f"- begin_to_valid_ms: {result['begin_to_valid_ms']}",
            f"- authored_input_bytes: {result['authored_input_bytes']}",
            f"- authored_semantic_bytes: {result['authored_semantic_bytes']}",
            f"- compile_ms: {result['compile_ms']}",
            f"- shard_plan_ms: {result['shard_plan_ms']}",
            f"- normalize_ms: {result['normalize_ms']}",
            f"- render_ms: {result['render_ms']}",
            f"- canonical_sha256: {result['canonical_sha256']}",
            "- semantic_match: true",
            "- rendered_match_authority: true",
    ]
    if result["render_artifact_kind"] == "single_board":
        lines.append(f"- board_sha256: {result['board_sha256']}")
    else:
        lines.extend(
            [
                "- render_artifact_kind: production_part_bundle",
                "- render_bundle_manifest_sha256: "
                + result["render_bundle_manifest_sha256"],
                "- render_bundle_aggregate_sha256: "
                + result["render_bundle_aggregate_sha256"],
            ]
        )
    lines.extend(
        [
            "",
            "The run directory evidence is authoritative. This callback is a compact mirror.",
            "",
        ]
    )
    return "\n".join(lines)


def submit_run(run_dir: Path) -> dict[str, Any]:
    state = load_state(run_dir)
    if state["status"] == "complete":
        authored = (run_dir / AUTHORED_FILE).read_bytes()
        digest = sha256_bytes(authored)
        if digest != state["result"]["authored_input_sha256"]:
            raise BenchmarkError("completed run cannot accept different authored input")
        return state
    if state["status"] == "failed":
        raise BenchmarkError("run exhausted its distinct submission attempts")
    if state["status"] != "started":
        raise BenchmarkError("submit requires begin to be recorded first")
    verify_run_locks(state)
    fixture_profile = state.get("fixture_profile", "q10")
    paths = profile_paths(fixture_profile)

    input_path = run_dir / AUTHORED_FILE
    try:
        authored = input_path.read_bytes()
    except OSError as exc:
        raise BenchmarkError(f"cannot read {input_path}: {exc}") from exc
    input_digest = sha256_bytes(authored)
    if state["attempts"] and state["attempts"][-1]["input_sha256"] == input_digest:
        last = state["attempts"][-1]
        if last["status"] == "invalid":
            raise BenchmarkError(f"unchanged invalid input: {last['error']}")

    attempt_number = len(state["attempts"]) + 1
    if attempt_number > state["attempt_limit"]:
        state["status"] = "failed"
        save_state(run_dir, state)
        raise BenchmarkError("submission attempt limit reached")

    attempts_dir = run_dir / "attempts"
    snapshot_path = attempts_dir / f"attempt-{attempt_number:03d}-input.json"
    if snapshot_path.exists():
        raise BenchmarkError(f"immutable attempt snapshot already exists: {snapshot_path}")
    atomic_write_bytes(snapshot_path, authored)

    submit_started_ns = time.perf_counter_ns()
    begin_ns = state["events"]["begin"]["perf_counter_ns"]
    attempt: dict[str, Any] = {
        "attempt": attempt_number,
        "submitted_at": utc_now(),
        "input_sha256": input_digest,
        "input_bytes": len(authored),
        "semantic_bytes": None,
        "begin_to_submit_ms": _elapsed_ms(begin_ns, submit_started_ns),
        "status": "invalid",
        "error": None,
    }

    try:
        try:
            text = authored.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BenchmarkError(f"authored input must be UTF-8: {exc}") from exc
        raw = loads_json_strict(text)
        attempt["semantic_bytes"] = len(canonical_json(raw).encode("utf-8"))

        compile_start = time.perf_counter_ns()
        if state["mode"] == "baseline_current_spec":
            compiled = validate_baseline(raw)
        else:
            compiled = compile_draft(raw)
        compile_end = time.perf_counter_ns()

        shard_plan_start = time.perf_counter_ns()
        compiled_questions = compiled.get("questions")
        if not isinstance(compiled_questions, list):
            raise BenchmarkError("compiled questions must be an array")
        shard_ranges = [
            (offset, min(offset + PRODUCTION_QUESTION_LIMIT, len(compiled_questions)))
            for offset in range(0, len(compiled_questions), PRODUCTION_QUESTION_LIMIT)
        ]
        shard_plan_end = time.perf_counter_ns()
        actual_part_counts = [end - start for start, end in shard_ranges]
        if len(compiled_questions) != state["question_count"]:
            raise BenchmarkError("compiled question count differs from fixture profile")
        if actual_part_counts != state["production_part_question_counts"]:
            raise BenchmarkError("compiled shard plan differs from fixture profile")

        normalize_start = time.perf_counter_ns()
        normalized = normalize_logical_spec(compiled)
        normalize_end = time.perf_counter_ns()
        golden = load_json_strict(paths["golden"])
        if normalized != golden:
            differences = difference_paths(golden, normalized)
            detail = "; ".join(differences) or "unknown semantic mismatch"
            raise BenchmarkError(f"normalized result differs from locked golden: {detail}")
        valid_ns = time.perf_counter_ns()

        render_start = time.perf_counter_ns()
        is_bundle = normalized.get("artifact_kind") == "benchmark_only_logical_bundle"
        if is_bundle:
            rendered_parts, render_manifest = _render_bundle(normalized)
            board_bytes = None
        else:
            rendered_parts = []
            render_manifest = None
            rendered_single = render_logical_parts(normalized)
            if len(rendered_single) != 1:
                raise BenchmarkError("single board render produced multiple documents")
            board_bytes = rendered_single[0].encode("utf-8")
        render_end = time.perf_counter_ns()
        canonical_bytes = (json.dumps(normalized, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
        atomic_write_json(run_dir / COMPILED_FILE, compiled)
        atomic_write_bytes(run_dir / CANONICAL_FILE, canonical_bytes)
        if is_bundle:
            assert render_manifest is not None
            for filename, body in rendered_parts:
                atomic_write_bytes(run_dir / filename, body)
            atomic_write_json(run_dir / BUNDLE_MANIFEST_FILE, render_manifest)
        else:
            assert board_bytes is not None
            atomic_write_bytes(run_dir / BOARD_FILE, board_bytes)

        dispatch_ns = state["events"]["dispatch"]["perf_counter_ns"]
        first_submit_ms = (
            state["attempts"][0]["begin_to_submit_ms"]
            if state["attempts"]
            else attempt["begin_to_submit_ms"]
        )
        attempt.update(
            {
                "status": "valid",
                "compile_ms": _elapsed_ms(compile_start, compile_end),
                "shard_plan_ms": _elapsed_ms(shard_plan_start, shard_plan_end),
                "normalize_ms": _elapsed_ms(normalize_start, normalize_end),
                "render_ms": _elapsed_ms(render_start, render_end),
            }
        )
        state["attempts"].append(attempt)
        state["status"] = "complete"
        state["completed_at"] = utc_now()
        state["result"] = {
            "first_pass": attempt_number == 1,
            "attempt_count": attempt_number,
            "dispatch_to_begin_ms": _elapsed_ms(
                dispatch_ns, state["events"]["begin"]["perf_counter_ns"]
            ),
            "begin_to_first_submit_ms": first_submit_ms,
            "begin_to_valid_ms": _elapsed_ms(begin_ns, valid_ns),
            "authored_input_bytes": len(authored),
            "authored_semantic_bytes": attempt["semantic_bytes"],
            "authored_input_sha256": input_digest,
            "compiled_semantic_bytes": len(canonical_json(compiled).encode("utf-8")),
            "question_count": len(compiled_questions),
            "production_part_question_counts": actual_part_counts,
            "canonical_bytes": len(canonical_bytes),
            "canonical_sha256": sha256_bytes(canonical_bytes),
            "compile_ms": attempt["compile_ms"],
            "shard_plan_ms": attempt["shard_plan_ms"],
            "normalize_ms": attempt["normalize_ms"],
            "render_ms": attempt["render_ms"],
        }
        if is_bundle:
            assert render_manifest is not None
            manifest_path = run_dir / BUNDLE_MANIFEST_FILE
            state["result"].update(
                {
                    "render_artifact_kind": "production_part_bundle",
                    "render_bundle_manifest_file": BUNDLE_MANIFEST_FILE,
                    "render_bundle_manifest_sha256": file_sha256(manifest_path),
                    "render_bundle_aggregate_sha256": render_manifest[
                        "aggregate_parts_sha256"
                    ],
                    "render_part_count": len(rendered_parts),
                    "render_part_files": [filename for filename, _ in rendered_parts],
                    "render_part_bytes": [len(body) for _, body in rendered_parts],
                    "render_part_sha256": [sha256_bytes(body) for _, body in rendered_parts],
                }
            )
        else:
            assert board_bytes is not None
            state["result"].update(
                {
                    "render_artifact_kind": "single_board",
                    "board_bytes": len(board_bytes),
                    "board_sha256": sha256_bytes(board_bytes),
                }
            )
        callback = _callback_markdown(state)
        atomic_write_text(run_dir / CALLBACK_FILE, callback)
        save_state(run_dir, state)
        return state
    except BenchmarkError as exc:
        attempt["error"] = str(exc)
        attempt["processing_ms"] = _elapsed_ms(submit_started_ns, time.perf_counter_ns())
        state["attempts"].append(attempt)
        if len(state["attempts"]) >= state["attempt_limit"]:
            state["status"] = "failed"
        save_state(run_dir, state)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--run-dir", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--mode", required=True, choices=sorted(MODES))
    prepare.add_argument(
        "--fixture-profile",
        choices=sorted(PROFILE_NAMES),
        default="q10",
    )
    prepare.add_argument("--thread-id", required=True)
    prepare.add_argument("--source-thread-id", required=True)

    for command in ("dispatch", "begin"):
        event = subparsers.add_parser(command)
        event.add_argument("--run-dir", required=True, type=Path)
        event.add_argument("--event-id", required=True)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--run-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "prepare":
            state = prepare_run(
                args.run_dir,
                run_id=args.run_id,
                mode=args.mode,
                thread_id=args.thread_id,
                source_thread_id=args.source_thread_id,
                fixture_profile=args.fixture_profile,
            )
        elif args.command in {"dispatch", "begin"}:
            state = mark_event(args.run_dir, args.command, args.event_id)
        else:
            state = submit_run(args.run_dir)
    except BenchmarkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"run_id": state["run_id"], "status": state["status"]}))
    if state["status"] == "complete":
        print(args.run_dir / CALLBACK_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
