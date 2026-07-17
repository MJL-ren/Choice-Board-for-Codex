#!/usr/bin/env python3
"""Render public fixtures and run every headless browser regression."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "skills" / "codex-choice-board" / "scripts" / "render_board.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def render(name: str, output_dir: Path) -> Path:
    source = FIXTURES / f"{name}.json"
    output = output_dir / f"{name}.html"
    run(
        [
            sys.executable,
            str(RENDERER),
            "--spec",
            str(source),
            "--output",
            str(output),
        ]
    )
    return output


def main() -> int:
    node = os.environ.get("NODE", "node")
    env = os.environ.copy()

    with tempfile.TemporaryDirectory(prefix="choice-board-browser-") as raw_temp:
        output_dir = Path(raw_temp)
        rendered = {
            name: render(name, output_dir)
            for name in (
                "board-ko",
                "board-ko-prefilled",
                "board-ko-completion",
                "board-ko-guided",
                "board-ko-guided-prefilled",
                "board-ko-guided-deferred",
                "board-ko-answer-notes",
                "board-ko-guided-answer-notes",
                "board-ko-guided-answer-notes-prefilled",
                "board-ko-guided-branch-candidate",
                "board-en",
                "board-en-guided-30",
                "board-fr-fallback-branching",
            )
        }

        run(
            [
                node,
                "tests/browser_smoke.cjs",
                str(rendered["board-ko"]),
                "",
                str(rendered["board-ko-prefilled"]),
                str(rendered["board-ko-completion"]),
            ],
            env=env,
        )
        run(
            [
                node,
                "tests/browser_guided_smoke.cjs",
                str(rendered["board-ko-guided"]),
                "",
                str(rendered["board-ko-guided-prefilled"]),
                str(rendered["board-ko-guided-deferred"]),
            ],
            env=env,
        )
        run(
            [
                node,
                "tests/browser_answer_notes_smoke.cjs",
                str(rendered["board-ko-answer-notes"]),
                str(rendered["board-ko-guided-answer-notes"]),
                str(rendered["board-ko-guided-answer-notes-prefilled"]),
            ],
            env=env,
        )
        run(
            [
                node,
                "tests/browser_branching_smoke.cjs",
                str(rendered["board-ko-guided-branch-candidate"]),
            ],
            env=env,
        )
        run(
            [
                node,
                "tests/browser_locale_scale_smoke.cjs",
                str(rendered["board-en"]),
                str(rendered["board-en-guided-30"]),
                str(rendered["board-fr-fallback-branching"]),
            ],
            env=env,
        )

    print("All Choice Board browser regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
