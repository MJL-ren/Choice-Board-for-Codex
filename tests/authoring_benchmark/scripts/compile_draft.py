#!/usr/bin/env python3
"""Benchmark wrapper around the shipped internal Board Draft expander."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from benchlib import BenchmarkError, atomic_write_json, load_json_strict


REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_SCRIPTS = REPO_ROOT / "skills" / "codex-choice-board" / "scripts"
sys.path.insert(0, str(PRODUCTION_SCRIPTS))

from compile_board_draft import DraftError, expand_draft  # noqa: E402


def compile_draft(raw: Any) -> dict[str, Any]:
    try:
        return expand_draft(raw)
    except DraftError as exc:
        raise BenchmarkError(str(exc)) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        compiled = compile_draft(load_json_strict(args.input))
        atomic_write_json(args.output, compiled)
    except BenchmarkError as exc:
        print(f"error: {exc}")
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
