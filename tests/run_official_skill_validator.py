#!/usr/bin/env python3
"""Run the pinned OpenAI skill-creator quick validator without vendoring it."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_SKILLS_COMMIT = "49f948faa9258a0c61caceaf225e179651397431"
VALIDATOR_SHA256 = "6cc9dc3199c935916cf6f73fcbbbb0e3bb1b58c8f5109fefa499978908164f51"
VALIDATOR_URL = (
    "https://raw.githubusercontent.com/openai/skills/"
    f"{OPENAI_SKILLS_COMMIT}/skills/.system/skill-creator/scripts/quick_validate.py"
)


def download_validator() -> bytes:
    request = Request(VALIDATOR_URL, headers={"User-Agent": "choice-board-validator/1"})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != VALIDATOR_SHA256:
        raise RuntimeError(
            "downloaded OpenAI validator hash mismatch: "
            f"expected {VALIDATOR_SHA256}, received {digest}"
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "skill",
        nargs="?",
        type=Path,
        default=Path("skills/codex-choice-board"),
        help="Skill directory to validate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill = args.skill.resolve()
    if not skill.is_dir():
        print(f"official skill validation failed: missing skill directory: {skill}", file=sys.stderr)
        return 2
    try:
        payload = download_validator()
        with tempfile.TemporaryDirectory(prefix="openai-skill-validator-") as directory:
            validator = Path(directory) / "quick_validate.py"
            validator.write_bytes(payload)
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(validator), str(skill)],
                check=False,
                text=True,
                capture_output=True,
            )
    except (HTTPError, URLError, OSError, RuntimeError) as error:
        print(f"official skill validation failed: {error}", file=sys.stderr)
        return 2
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
