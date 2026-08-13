import unittest
from unittest.mock import Mock, patch

from growth.engagement_hooks import enhance_post_text
from src import main


class TelegramFormatTests(unittest.TestCase):
    def test_existing_question_is_not_duplicated(self):
        result = enhance_post_text("Полезный совет. Уже пробовали?", "технологии")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)

    def test_photo_caption_fits_single_telegram_post(self):
        caption = main._telegram_photo_caption("Текст. " * 500, "https://example.com/full")
        self.assertLessEqual(len(caption), 1000)
        self.assertIn("Читать полностью", caption)

    @patch.object(main, "TELEGRAM_BOT_TOKEN", "token")
    @patch.object(main, "TELEGRAM_CHAT_ID", "@channel")
    @patch("src.image_provider.download_watermarked", return_value=(b"image", "image/jpeg", ".jpg"))
    @patch("src.main.requests.post")
    def test_image_and_text_are_sent_as_one_photo_post(self, post, _download):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"result": {"message_id": 77}}
        post.return_value = response

        ok, message_id = main.publish_to_telegram(
            "Заголовок", "<p>Полезный текст.</p>", "https://example.com/image.jpg",
            article_url="https://example.com/article", niche="технологии"
        )

        self.assertTrue(ok)
        self.assertEqual(message_id, 77)
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith("/sendPhoto"))
        self.assertIn("Читать полностью", post.call_args.kwargs["data"]["caption"])

    def test_missing_question_gets_single_engagement_footer(self):
        result = enhance_post_text("Полезный совет", "технологии", "Тест")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)


if __name__ == "__main__":
    unittest.main()
