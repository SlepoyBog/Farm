import unittest

from src.content_validator import (
    check_html_integrity,
    fix_truncated_html,
    validate_and_fix,
)


class ContentValidatorTests(unittest.TestCase):
    def test_valid_complete_html_is_unchanged(self):
        source = "<p>Привет мир. Это полный текст.</p>"
        result, issues = validate_and_fix(source)
        self.assertEqual(result, source)
        self.assertEqual(issues, [])

    def test_text_without_final_punctuation_is_not_destroyed(self):
        source = "<p>Заголовок или короткая подпись без точки</p>"
        result, issues = validate_and_fix(source)
        self.assertEqual(result, source)
        self.assertEqual(issues, [])

    def test_strong_mid_word_signal_is_trimmed_to_sentence(self):
        source = "<p>Привет мир. Это текст который оборван на сло</p>"
        result, issues = validate_and_fix(source)
        self.assertEqual(result, "<p>Привет мир.</p>")
        self.assertIn("Fixed truncated ending", issues)

    def test_mismatched_tags_are_balanced_without_duplicates(self):
        source = "<p>Привет.<b> Полный текст.</p>"
        result, issues = validate_and_fix(source)
        self.assertEqual(result, "<p>Привет.<b> Полный текст.</b></p>")
        self.assertTrue(issues)
        self.assertTrue(check_html_integrity(result)[0])

    def test_void_elements_are_valid(self):
        for source in (
            '<p>Hello<br/>World</p>',
            '<p>Hello<img src="x.jpg" />World</p>',
            "<div><br><hr></div>",
        ):
            with self.subTest(source=source):
                self.assertTrue(check_html_integrity(source)[0])

    def test_truncation_preserves_container_tags(self):
        self.assertEqual(
            fix_truncated_html("<p>Полный текст. Обрыв сло</p>"),
            "<p>Полный текст.</p>",
        )

    def test_length_limit_produces_valid_html(self):
        source = "<p>" + ("Полное предложение. " * 100) + "</p>"
        result, issues = validate_and_fix(source, max_chars=300)
        self.assertLessEqual(len(result), 300)
        self.assertIn("Truncated to 300 chars", issues)
        self.assertTrue(check_html_integrity(result)[0])


if __name__ == "__main__":
    unittest.main()
