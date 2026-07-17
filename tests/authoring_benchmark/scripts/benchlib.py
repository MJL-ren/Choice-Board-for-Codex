#!/usr/bin/env python3
"""Shared primitives for the isolated Choice Board authoring benchmark."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


BENCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BENCH_ROOT.parents[1]
RENDERER_PATH = (
    REPO_ROOT / "skills" / "codex-choice-board" / "scripts" / "render_board.py"
)
TEMPLATE_PATH = (
    REPO_ROOT
    / "skills"
    / "codex-choice-board"
    / "assets"
    / "choice-board-template.html"
)
AUTHORITY_PATH = BENCH_ROOT / "fixture_authority.json"
FIXTURE_PATH = BENCH_ROOT / "FIXTURE_10Q.md"
GOLDEN_PATH = BENCH_ROOT / "GOLDEN_CANONICAL.json"
MANIFEST_PATH = BENCH_ROOT / "BENCHMARK_MANIFEST.json"
EXTRA_15Q_PATH = BENCH_ROOT / "fixture_extra_questions_15q.json"
PROFILE_NAMES = {"q05", "q10", "q15"}
PRODUCTION_QUESTION_LIMIT = 12
BENCHMARK_LOGICAL_LIMIT = 15
SHARD_ALGORITHM_VERSION = 1
SHARD_ALGORITHM_DESCRIPTOR = (
    "choice-board-authoring-benchmark/contiguous-after-authoring/"
    "production-max-12/unique-form-id-double-hyphen/v1"
)
SHARD_ALGORITHM_SHA256 = hashlib.sha256(
    SHARD_ALGORITHM_DESCRIPTOR.encode("utf-8")
).hexdigest()


class BenchmarkError(ValueError):
    """Raised when benchmark evidence or input violates the locked contract."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BenchmarkError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_json_strict(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_strict_object)
    except BenchmarkError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BenchmarkError(f"invalid JSON: {exc}") from exc


def load_json_strict(path: Path) -> Any:
    try:
        return loads_json_strict(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BenchmarkError(f"cannot read {path}: {exc}") from exc


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise BenchmarkError(f"cannot hash {path}: {exc}") from exc


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, pretty_json(value))


_RENDERER: ModuleType | None = None


def load_renderer() -> ModuleType:
    global _RENDERER
    if _RENDERER is not None:
        return _RENDERER
    spec = importlib.util.spec_from_file_location(
        "choice_board_benchmark_renderer", RENDERER_PATH
    )
    if spec is None or spec.loader is None:
        raise BenchmarkError(f"cannot import renderer: {RENDERER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RENDERER = module
    return module


def normalize_spec(raw: Any) -> dict[str, Any]:
    module = load_renderer()
    try:
        return module.normalize_spec(raw)
    except Exception as exc:
        if exc.__class__.__name__ == "SpecError":
            raise BenchmarkError(str(exc)) from exc
        raise


def render_normalized(spec: dict[str, Any]) -> str:
    module = load_renderer()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    try:
        return module.render_fragment(spec, template)
    except Exception as exc:
        if exc.__class__.__name__ == "SpecError":
            raise BenchmarkError(str(exc)) from exc
        raise


def profile_paths(profile: str) -> dict[str, Path]:
    if profile not in PROFILE_NAMES:
        raise BenchmarkError(
            f"fixture profile must be one of: {', '.join(sorted(PROFILE_NAMES))}"
        )
    if profile == "q10":
        return {
            "fixture": FIXTURE_PATH,
            "golden": GOLDEN_PATH,
            "manifest": MANIFEST_PATH,
        }
    root = BENCH_ROOT / "profiles" / profile
    return {
        "fixture": root / "FIXTURE.md",
        "golden": root / "GOLDEN_CANONICAL.json",
        "manifest": root / "MANIFEST.json",
    }


def normalize_logical_spec(raw: Any) -> dict[str, Any]:
    """Normalize one logical board, sharding only benchmark stress inputs.

    A returned bundle is benchmark evidence, not a production Choice Board.
    Every part still passes through the unchanged production normalizer.
    """
    if not isinstance(raw, dict):
        raise BenchmarkError("the logical spec must be a JSON object")
    questions = raw.get("questions")
    if not isinstance(questions, list):
        raise BenchmarkError("logical questions must be an array")
    if len(questions) <= PRODUCTION_QUESTION_LIMIT:
        return normalize_spec(raw)
    if len(questions) > BENCHMARK_LOGICAL_LIMIT:
        raise BenchmarkError(
            f"benchmark logical questions must not exceed {BENCHMARK_LOGICAL_LIMIT}"
        )
    form_id = raw.get("form_id")
    if not isinstance(form_id, str):
        raise BenchmarkError("logical form_id must be a string")

    # The production normalizer catches duplicates inside one part. Check the
    # complete logical input before sharding so a duplicate across 12/3 cannot
    # escape as two individually valid production boards.
    seen_question_ids: set[str] = set()
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise BenchmarkError(f"logical questions[{index}] must be an object")
        question_id = question.get("id")
        if not isinstance(question_id, str):
            raise BenchmarkError(f"logical questions[{index}].id must be a string")
        if question_id in seen_question_ids:
            raise BenchmarkError(f"duplicate question id: {question_id}")
        seen_question_ids.add(question_id)

    parts: list[dict[str, Any]] = []
    for part_index, offset in enumerate(
        range(0, len(questions), PRODUCTION_QUESTION_LIMIT), start=1
    ):
        part = dict(raw)
        part["form_id"] = f"{form_id}--part-{part_index:02d}"
        part["questions"] = questions[offset : offset + PRODUCTION_QUESTION_LIMIT]
        parts.append(normalize_spec(part))
    return {
        "bundle_schema_version": 1,
        "artifact_kind": "benchmark_only_logical_bundle",
        "logical_form_id": form_id,
        "question_count": len(questions),
        "production_question_limit": PRODUCTION_QUESTION_LIMIT,
        "shard_algorithm_version": SHARD_ALGORITHM_VERSION,
        "shard_algorithm_sha256": SHARD_ALGORITHM_SHA256,
        "parts": parts,
    }


def logical_questions(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    if normalized.get("artifact_kind") == "benchmark_only_logical_bundle":
        return [
            question
            for part in normalized["parts"]
            for question in part["questions"]
        ]
    return normalized["questions"]


def normalized_parts(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered production-normalized parts for rendering."""
    if normalized.get("artifact_kind") == "benchmark_only_logical_bundle":
        parts = normalized.get("parts")
        if not isinstance(parts, list) or not parts:
            raise BenchmarkError("benchmark bundle parts must be a non-empty array")
        return parts
    return [normalized]


def render_logical_parts(normalized: dict[str, Any]) -> list[str]:
    """Render every production part separately; never concatenate documents."""
    return [render_normalized(part) for part in normalized_parts(normalized)]


def difference_paths(expected: Any, actual: Any, prefix: str = "$") -> list[str]:
    differences: list[str] = []
    if type(expected) is not type(actual):
        return [f"{prefix}: expected {type(expected).__name__}, got {type(actual).__name__}"]
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            child = f"{prefix}.{key}"
            if key not in expected:
                differences.append(f"{child}: unexpected")
            elif key not in actual:
                differences.append(f"{child}: missing")
            else:
                differences.extend(difference_paths(expected[key], actual[key], child))
            if len(differences) >= 12:
                break
        return differences[:12]
    if isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append(
                f"{prefix}: expected {len(expected)} items, got {len(actual)}"
            )
        for index, (left, right) in enumerate(zip(expected, actual)):
            differences.extend(difference_paths(left, right, f"{prefix}[{index}]"))
            if len(differences) >= 12:
                break
        return differences[:12]
    if expected != actual:
        differences.append(f"{prefix}: expected {expected!r}, got {actual!r}")
    return differences[:12]


def require_exact_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BenchmarkError(f"unknown {label} fields: {', '.join(unknown)}")
