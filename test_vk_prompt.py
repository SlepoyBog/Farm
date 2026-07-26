import unittest
from pathlib import Path


PROMPT_PATH = Path(__file__).parent / "prompts" / "vk_trend_editor.prompter"


class VkPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def test_keeps_required_template_variables(self):
        self.assertIn("{{article}}", self.prompt)
        self.assertIn("{{niche}}", self.prompt)

    def test_requires_subscriber_call_to_action(self):
        self.assertIn("Подпишитесь на НейроПоток", self.prompt)

    def test_limits_clickbait_and_unsupported_facts(self):
        self.assertIn("Не выдумывай", self.prompt)
        self.assertIn("кликбейт", self.prompt.lower())

    def test_has_vk_readability_constraints(self):
        self.assertIn("900–1400 символов", self.prompt)
        self.assertIn("не более двух предложений", self.prompt)
        self.assertIn("Не добавляй хештеги", self.prompt)


if __name__ == "__main__":
    unittest.main()
