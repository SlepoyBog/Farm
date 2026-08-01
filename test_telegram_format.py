import unittest

from growth.engagement_hooks import enhance_post_text


class TelegramFormatTests(unittest.TestCase):
    def test_existing_question_is_not_duplicated(self):
        result = enhance_post_text("Полезный совет. Уже пробовали?", "технологии")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)

    def test_missing_question_gets_single_engagement_footer(self):
        result = enhance_post_text("Полезный совет", "технологии", "Тест")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)


if __name__ == "__main__":
    unittest.main()
