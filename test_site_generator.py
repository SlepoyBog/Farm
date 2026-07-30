import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import src.site_generator as site_generator


class SiteGeneratorRssTests(unittest.TestCase):
    def test_rss_uses_absolute_https_item_urls(self):
        article = {
            "title": "Тестовая статья",
            "slug": "test-article",
            "content": "<p>Описание статьи.</p>",
            "mtime": datetime(2026, 7, 28, tzinfo=timezone.utc),
            "og_image": "https://example.com/image.jpg",
        }

        old_dir = site_generator.SITE_DIR
        old_url = site_generator.SITE_URL
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                site_generator.SITE_DIR = Path(temp_dir)
                site_generator.SITE_URL = site_generator.DEFAULT_SITE_URL
                site_generator._generate_rss([article])
                rss = (Path(temp_dir) / "rss.xml").read_text(encoding="utf-8")
        finally:
            site_generator.SITE_DIR = old_dir
            site_generator.SITE_URL = old_url

        expected = "https://slepoybog.github.io/Farm/test-article.html"
        self.assertIn(f"<link>{expected}</link>", rss)
        self.assertIn(f"<guid>{expected}</guid>", rss)
        self.assertIn(
            '<atom:link href="https://slepoybog.github.io/Farm/rss.xml"',
            rss,
        )

    def test_rss_description_does_not_cut_mid_sentence(self):
        paragraph = "Это законченное предложение. " * 180

        result = site_generator._rss_description(f"<p>{paragraph}</p>", 500)

        self.assertLessEqual(len(result), 500)
        self.assertGreater(len(result), 250)
        self.assertTrue(result.endswith("."))
        self.assertNotIn("<p>", result)

    def test_rss_description_preserves_paragraphs_and_lists(self):
        content = (
            "<h2>Что проверить</h2>"
            "<p>Первый абзац.</p>"
            "<ul><li>Первый пункт</li><li>Второй пункт</li></ul>"
            "<p>Последний абзац.</p>"
        )

        result = site_generator._rss_description(content)

        self.assertEqual(
            result,
            "Что проверить\n\n"
            "Первый абзац.\n\n"
            "• Первый пункт\n"
            "• Второй пункт\n\n"
            "Последний абзац.",
        )

    def test_rss_prefers_prepared_vk_text(self):
        article = {
            "title": "Тест",
            "slug": "test",
            "content": "<p>Текст статьи.</p>",
            "mtime": datetime(2026, 7, 28, tzinfo=timezone.utc),
            "og_image": "",
            "vk_text": "Заход варианта B.\n\n• Первый шаг\n• Второй шаг",
        }
        old_dir = site_generator.SITE_DIR
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                site_generator.SITE_DIR = Path(temp_dir)
                site_generator._generate_rss([article])
                rss = (Path(temp_dir) / "rss.xml").read_text(encoding="utf-8")
        finally:
            site_generator.SITE_DIR = old_dir

        self.assertIn("Заход варианта B.", rss)
        self.assertIn("• Первый шаг", rss)
        self.assertIn(
            "<description>Заход варианта B.\n\n"
            "• Первый шаг\n• Второй шаг</description>",
            rss,
        )


if __name__ == "__main__":
    unittest.main()
