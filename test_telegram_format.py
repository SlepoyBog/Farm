import unittest
from unittest.mock import Mock, patch

from growth.engagement_hooks import enhance_post_text
from src import main


class TelegramFormatTests(unittest.TestCase):
    def test_existing_question_is_not_duplicated(self):
        result = enhance_post_text("Полезный совет. Уже пробовали?", "технологии")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)

    def test_post_text_is_never_truncated(self):
        source = "Текст. " * 500
        result = main._telegram_post_text(source, "https://example.com/full")
        self.assertIn(source.strip(), result)
        self.assertIn("Читать полностью", result)

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

    @patch.object(main, "TELEGRAM_BOT_TOKEN", "token")
    @patch.object(main, "TELEGRAM_CHAT_ID", "@channel")
    @patch("src.image_provider.download_watermarked")
    @patch("src.main.requests.post")
    def test_long_post_is_sent_once_as_complete_text(self, post, download):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"result": {"message_id": 78}}
        post.return_value = response
        long_text = "Полный абзац без обрезания. " * 60

        ok, message_id = main.publish_to_telegram(
            "Заголовок", f"<p>{long_text}</p>", "https://example.com/image.jpg",
            article_url="https://example.com/article", niche="технологии"
        )

        self.assertTrue(ok)
        self.assertEqual(message_id, 78)
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith("/sendMessage"))
        payload = post.call_args.kwargs["json"]
        self.assertIn(long_text.strip(), payload["text"])
        self.assertIn("https://example.com/article", payload["text"])
        self.assertEqual(payload["link_preview_options"]["url"], "https://example.com/article")
        self.assertTrue(payload["link_preview_options"]["prefer_large_media"])
        self.assertTrue(payload["link_preview_options"]["show_above_text"])
        download.assert_not_called()

    @patch.object(main, "TELEGRAM_BOT_TOKEN", "token")
    @patch.object(main, "TELEGRAM_CHAT_ID", "@channel")
    @patch("src.main.requests.post")
    def test_oversized_post_is_rejected_instead_of_truncated(self, post):
        ok, message_id = main.publish_to_telegram(
            "Заголовок", f"<p>{'Текст ' * 1000}</p>", niche="технологии"
        )
        self.assertFalse(ok)
        self.assertIsNone(message_id)
        post.assert_not_called()

    def test_missing_question_gets_single_engagement_footer(self):
        result = enhance_post_text("Полезный совет", "технологии", "Тест")

        self.assertEqual(result.count("?"), 1)
        self.assertIn("Сохраните пост", result)


if __name__ == "__main__":
    unittest.main()
