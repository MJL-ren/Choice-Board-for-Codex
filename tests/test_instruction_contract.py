from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "codex-choice-board"
SKILL = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"
ACTIVATION = SKILL_DIR / "references" / "activation.md"
AUTHORING_DRAFT = SKILL_DIR / "references" / "authoring-draft.md"
RESPONSE_HANDLING = SKILL_DIR / "references" / "response-handling.md"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


class InstructionContractTests(unittest.TestCase):
    def test_reference_links_resolve_and_receiver_is_conditional(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\((references/[^)]+\.md)\)", skill)

        self.assertEqual(
            sorted(links),
            sorted(
                [
                    "references/activation.md",
                    "references/authoring-draft.md",
                    "references/response-handling.md",
                    "references/schema.md",
                ]
            ),
        )
        for link in links:
            self.assertTrue((SKILL_DIR / link).is_file(), link)

        before_receive, receive_and_after = skill.split("## Receive", maxsplit=1)
        receive, _ = receive_and_after.split("## Plain-text fallback", maxsplit=1)
        self.assertNotIn("response-handling.md", before_receive)
        self.assertEqual(receive.count("(references/response-handling.md)"), 1)
        self.assertIn("actual user message", receive)
        self.assertIn("CHOICE_BOARD_SUBMISSION", receive)
        self.assertIn("CHOICE_BOARD_EXPLANATION_REQUEST", receive)
        self.assertIn("before using any answer", receive)

    def test_openai_metadata_keeps_discovery_contract(self) -> None:
        metadata = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertRegex(
            metadata,
            r'(?m)^\s*default_prompt:\s*"[^"]*\$codex-choice-board[^"]*"\s*$',
        )
        self.assertEqual(metadata.count("policy:"), 1)
        self.assertEqual(metadata.count("allow_implicit_invocation: true"), 1)
        self.assertNotIn("allow_implicit_invocation: false", metadata)

    def test_embedded_draft_example_compiles(self) -> None:
        markdown = AUTHORING_DRAFT.read_text(encoding="utf-8")
        match = re.search(r"```json\s*(\{.*?\})\s*```", markdown, re.DOTALL)
        self.assertIsNotNone(match)

        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        try:
            from compile_board_draft import compile_draft

            compiled = compile_draft(json.loads(match.group(1)))
        finally:
            sys.path.pop(0)

        self.assertEqual(compiled["schema_version"], 2)
        self.assertEqual(compiled["presentation"], "stepper")
        self.assertEqual(len(compiled["questions"]), 4)

    def test_response_module_preserves_receiver_state_contracts(self) -> None:
        response = RESPONSE_HANDLING.read_text(encoding="utf-8")
        required_literals = [
            "CHOICE_BOARD_SUBMISSION",
            "CHOICE_BOARD_EXPLANATION_REQUEST",
            "validate_envelope.py",
            "--previous-message",
            "--allow-legacy-missing-submission-id",
            "do not claim duplicate protection",
            "canonical JSON payload is authoritative",
            "pause_now",
            "draft_answers",
            "draft_other_answers",
            "draft_answer_notes",
            "draft_skipped_question_ids",
            "initial_question_id",
            "flow_digest",
            "after_completion",
            "completion_parent",
            "parent fields",
            "`answers`, `other_answers`, and `answer_notes`",
            "remove its earlier provisional Other text",
            "Unchanged answers reuse the exact prompt and `submission_id`",
            "Never retry automatically",
        ]
        for literal in required_literals:
            self.assertIn(literal, response, literal)

        self.assertIn("type-neutral value", response)
        self.assertIn("remove original `show_if`", response)
        self.assertIn("`allow_skip: false`", response)
        self.assertIn("exactly the deferred question IDs", response)

    def test_instruction_word_budgets(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        frontmatter_match = re.match(r"---\s*(.*?)\s*---\s*(.*)", skill, re.DOTALL)
        self.assertIsNotNone(frontmatter_match)
        description_match = re.search(
            r'(?m)^description:\s*"(.*)"\s*$', frontmatter_match.group(1)
        )
        self.assertIsNotNone(description_match)

        self.assertLessEqual(word_count(description_match.group(1)), 65)
        self.assertLessEqual(word_count(frontmatter_match.group(2)), 1500)
        self.assertLessEqual(word_count(ACTIVATION.read_text(encoding="utf-8")), 260)
        self.assertLessEqual(word_count(AUTHORING_DRAFT.read_text(encoding="utf-8")), 280)
        self.assertLessEqual(word_count(RESPONSE_HANDLING.read_text(encoding="utf-8")), 750)


if __name__ == "__main__":
    unittest.main()
