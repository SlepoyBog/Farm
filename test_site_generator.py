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


if __name__ == "__main__":
    unittest.main()
