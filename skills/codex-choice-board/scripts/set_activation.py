#!/usr/bin/env python3
"""Set or inspect the Choice Board activation mode safely."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


MODES = {"explicit", "suggest", "auto"}
POLICY_HEADER_RE = re.compile(r"^policy:\s*(?:#.*)?$")
TOP_LEVEL_POLICY_RE = re.compile(r"^policy\s*:")
POLICY_SETTING_RE = re.compile(
    r"^[ \t]+allow_implicit_invocation:\s*(true|false)\s*(?:#.*)?$"
)


class PolicyError(RuntimeError):
    pass


def default_settings_path() -> Path:
    base = Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else Path.home() / ".codex"
    return base / "codex-choice-board" / "settings.json"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_mode(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "explicit", "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "explicit", "invalid"
    if not isinstance(value, dict):
        return "explicit", "invalid"
    schema_version = value.get("schema_version")
    activation_mode = value.get("activation_mode")
    if (
        type(schema_version) is not int
        or schema_version != 1
        or not isinstance(activation_mode, str)
        or activation_mode not in MODES
    ):
        return "explicit", "invalid"
    return activation_mode, "valid"


def inspect_policy_text(text: str) -> tuple[list[str], int | None, int | None, tuple[int, bool] | None]:
    lines = text.splitlines()
    policy_headers = [
        index
        for index, line in enumerate(lines)
        if line and not line[0].isspace() and TOP_LEVEL_POLICY_RE.match(line)
    ]
    if len(policy_headers) > 1:
        raise PolicyError("openai.yaml contains more than one top-level policy block")
    if not policy_headers:
        return lines, None, None, None

    policy_index = policy_headers[0]
    if not POLICY_HEADER_RE.fullmatch(lines[policy_index]):
        raise PolicyError("openai.yaml policy must use a top-level block")

    block_end = len(lines)
    for index in range(policy_index + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped and not stripped.startswith("#") and not lines[index][0].isspace():
            block_end = index
            break

    setting_candidates = [
        index
        for index in range(policy_index + 1, block_end)
        if lines[index].lstrip().startswith("allow_implicit_invocation:")
    ]
    if len(setting_candidates) > 1:
        raise PolicyError("openai.yaml contains duplicate allow_implicit_invocation values")
    if not setting_candidates:
        return lines, policy_index, block_end, None

    setting_index = setting_candidates[0]
    match = POLICY_SETTING_RE.fullmatch(lines[setting_index])
    if not match:
        raise PolicyError("openai.yaml allow_implicit_invocation must be true or false")
    return lines, policy_index, block_end, (setting_index, match.group(1) == "true")


def read_policy(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        _, policy_index, _, setting = inspect_policy_text(path.read_text(encoding="utf-8"))
    except (OSError, PolicyError):
        return False, "invalid"
    if policy_index is None or setting is None:
        return False, "missing"
    return setting[1], "valid"


def update_policy(path: Path, allow_implicit: bool) -> None:
    text = path.read_text(encoding="utf-8")
    lines, policy_index, _, setting = inspect_policy_text(text)
    value_line = f"  allow_implicit_invocation: {'true' if allow_implicit else 'false'}"

    if policy_index is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(["policy:", value_line])
    else:
        if setting is None:
            lines.insert(policy_index + 1, value_line)
        else:
            setting_index = setting[0]
            lines[setting_index] = value_line

    atomic_write(path, "\n".join(lines).rstrip() + "\n")


def write_settings(path: Path, mode: str) -> None:
    content = json.dumps(
        {"schema_version": 1, "activation_mode": mode},
        ensure_ascii=False,
        indent=2,
    )
    atomic_write(path, content + "\n")


def activation_state(settings_path: Path, openai_yaml: Path) -> dict[str, object]:
    configured_mode, settings_state = read_mode(settings_path)
    allow_implicit, policy_state = read_policy(openai_yaml)
    # Natural-language direct requests need the skill to remain discoverable in
    # every mode. The inner setting, not this outer injection gate, controls
    # ambient suggest/auto behavior after the skill is loaded.
    expected_policy = True
    consistent = (
        settings_state == "valid"
        and policy_state == "valid"
        and allow_implicit == expected_policy
    )
    effective_mode = configured_mode if consistent else "explicit"
    return {
        "configured_mode": configured_mode,
        "effective_mode": effective_mode,
        "settings_state": settings_state,
        "allow_implicit_invocation": allow_implicit,
        "policy_state": policy_state,
        "consistent": consistent,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["explicit", "suggest", "auto", "show"])
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Installed skill directory",
    )
    parser.add_argument("--settings-path", type=Path, default=default_settings_path())
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    openai_yaml = args.skill_dir / "agents" / "openai.yaml"

    try:
        if args.mode == "show":
            result = activation_state(args.settings_path, openai_yaml)
        else:
            mode = args.mode
            allow_implicit = True
            if mode == "explicit":
                update_policy(openai_yaml, allow_implicit)
                write_settings(args.settings_path, mode)
            else:
                write_settings(args.settings_path, mode)
                update_policy(openai_yaml, allow_implicit)
            result = activation_state(args.settings_path, openai_yaml)
            if result["configured_mode"] != mode or not result["consistent"]:
                raise RuntimeError("activation files did not verify after writing")
            result["metadata_reload_may_be_required"] = True
    except (OSError, RuntimeError) as exc:
        print(f"choice-board activation failed: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        mode_label = {
            "explicit": "only when called directly",
            "suggest": "ask before opening when it would help",
            "auto": "open automatically when it fits",
        }[result["effective_mode"]]
        print(f"Choice Board is set to {mode_label}.")
        if not result["consistent"]:
            print("A setting was missing or inconsistent, so it failed closed to direct calls only.")
        if args.mode != "show":
            print("Open a new task or restart Codex if the current task still uses the previous setting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
