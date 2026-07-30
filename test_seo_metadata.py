import json
import tempfile
import unittest
from pathlib import Path

from src.seo_optimizer import SEOData, save_metadata


class SeoMetadataTests(unittest.TestCase):
    def test_preserves_vk_experiment_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            meta_path = output_dir / "test.meta.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "niche": "искусственный интеллект",
                        "image_url": "https://example.com/image.jpg",
                        "vk_text": "Готовый текст VK",
                        "ab_variant": "B",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            save_metadata(
                "test",
                "Тема",
                SEOData(
                    "SEO title",
                    "SEO description",
                    "ai, prompt",
                    "<p>Статья</p>",
                ),
                output_dir=output_dir,
            )

            stored = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["vk_text"], "Готовый текст VK")
            self.assertEqual(stored["ab_variant"], "B")
            self.assertEqual(stored["niche"], "искусственный интеллект")
            self.assertEqual(stored["seo_title"], "SEO title")


if __name__ == "__main__":
    unittest.main()
