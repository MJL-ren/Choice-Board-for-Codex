from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "codex-choice-board" / "scripts" / "set_activation.py"
SOURCE_YAML = ROOT / "skills" / "codex-choice-board" / "agents" / "openai.yaml"


class ActivationTests(unittest.TestCase):
    def run_mode(self, mode: str, skill_dir: Path, settings: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                mode,
                "--skill-dir",
                str(skill_dir),
                "--settings-path",
                str(settings),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_modes_update_inner_setting_and_outer_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "skill"
            agents = skill_dir / "agents"
            agents.mkdir(parents=True)
            yaml_path = agents / "openai.yaml"
            yaml_path.write_text(SOURCE_YAML.read_text(encoding="utf-8"), encoding="utf-8")
            settings = Path(directory) / "settings.json"

            for mode, allowed in (("suggest", True), ("auto", True), ("explicit", False)):
                result = self.run_mode(mode, skill_dir, settings)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["configured_mode"], mode)
                self.assertEqual(payload["effective_mode"], mode)
                self.assertTrue(payload["consistent"])
                self.assertEqual(payload["allow_implicit_invocation"], allowed)
                yaml_text = yaml_path.read_text(encoding="utf-8")
                expected = f"allow_implicit_invocation: {'true' if allowed else 'false'}"
                self.assertIn(expected, yaml_text)
                saved = json.loads(settings.read_text(encoding="utf-8"))
                self.assertEqual(saved["activation_mode"], mode)

    def test_missing_or_invalid_settings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "skill"
            agents = skill_dir / "agents"
            agents.mkdir(parents=True)
            (agents / "openai.yaml").write_text(SOURCE_YAML.read_text(encoding="utf-8"), encoding="utf-8")
            settings = Path(directory) / "settings.json"

            missing = self.run_mode("show", skill_dir, settings)
            missing_payload = json.loads(missing.stdout)
            self.assertEqual(missing_payload["effective_mode"], "explicit")
            self.assertFalse(missing_payload["consistent"])
            settings.write_text("not json", encoding="utf-8")
            invalid = self.run_mode("show", skill_dir, settings)
            invalid_payload = json.loads(invalid.stdout)
            self.assertEqual(invalid_payload["effective_mode"], "explicit")
            self.assertFalse(invalid_payload["consistent"])

            settings.write_text(
                json.dumps({"schema_version": True, "activation_mode": "auto"}),
                encoding="utf-8",
            )
            boolean_version = self.run_mode("show", skill_dir, settings)
            boolean_payload = json.loads(boolean_version.stdout)
            self.assertEqual(boolean_payload["effective_mode"], "explicit")
            self.assertEqual(boolean_payload["settings_state"], "invalid")

            settings.write_text(
                json.dumps({"schema_version": 1, "activation_mode": []}),
                encoding="utf-8",
            )
            list_mode = self.run_mode("show", skill_dir, settings)
            list_payload = json.loads(list_mode.stdout)
            self.assertEqual(list_mode.returncode, 0)
            self.assertEqual(list_payload["effective_mode"], "explicit")
            self.assertEqual(list_payload["settings_state"], "invalid")

    def test_outer_inner_mismatch_reports_effective_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "skill"
            agents = skill_dir / "agents"
            agents.mkdir(parents=True)
            (agents / "openai.yaml").write_text(SOURCE_YAML.read_text(encoding="utf-8"), encoding="utf-8")
            settings = Path(directory) / "settings.json"
            settings.write_text(
                json.dumps({"schema_version": 1, "activation_mode": "auto"}),
                encoding="utf-8",
            )

            shown = self.run_mode("show", skill_dir, settings)
            payload = json.loads(shown.stdout)
            self.assertEqual(payload["configured_mode"], "auto")
            self.assertEqual(payload["effective_mode"], "explicit")
            self.assertFalse(payload["consistent"])
            self.assertFalse(payload["allow_implicit_invocation"])

    def test_duplicate_policy_blocks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "skill"
            agents = skill_dir / "agents"
            agents.mkdir(parents=True)
            yaml = SOURCE_YAML.read_text(encoding="utf-8") + "\npolicy:\n  allow_implicit_invocation: true\n"
            (agents / "openai.yaml").write_text(yaml, encoding="utf-8")
            settings = Path(directory) / "settings.json"

            result = self.run_mode("auto", skill_dir, settings)
            self.assertEqual(result.returncode, 2)
            self.assertIn("more than one top-level policy block", result.stderr)


if __name__ == "__main__":
    unittest.main()
