import unittest
from unittest.mock import Mock, patch

from src.vk_publisher import publish_to_vk


def _vk_response(payload):
    response = Mock()
    response.status_code = 200
    response.text = '{"response": {}}'
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class VkPublisherTests(unittest.TestCase):
    @patch.dict("os.environ", {"VK_PUBLISH_ENABLED": "false"})
    @patch("src.vk_publisher.requests.post")
    def test_direct_publish_stays_enabled_after_rss_service_expires(self, post):
        post.return_value = _vk_response({"response": {"post_id": 41}})
        ok, post_id = publish_to_vk(
            "token",
            "club123",
            "Заголовок",
            "<p>Текст</p>",
            "технологии",
            random_id=1001,
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 41)
        post.assert_called_once()

    @patch("src.vk_publisher.requests.post")
    @patch("src.vk_publisher._upload_wall_photo", return_value=None)
    def test_skips_image_by_default_for_group_token(self, upload, post):
        post.return_value = _vk_response({"response": {"post_id": 42}})

        ok, post_id = publish_to_vk(
            "token",
            "club123",
            "Заголовок",
            "<p>Текст</p>",
            "технологии",
            image_url="https://images.example/cover.jpg",
            random_id=1002,
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 42)
        upload.assert_not_called()
        self.assertNotIn("attachments", post.call_args.kwargs["data"])

    @patch.dict("os.environ", {"VK_PUBLISH_IMAGES": "true"})
    @patch("src.vk_publisher.requests.post")
    @patch("src.vk_publisher._upload_wall_photo", return_value=None)
    def test_retries_without_attachment_if_vk_rejects_external_url(self, _, post):
        post.side_effect = [
            _vk_response({"error": {"error_code": 100, "error_msg": "Bad attachment"}}),
            _vk_response({"response": {"post_id": 43}}),
        ]

        ok, post_id = publish_to_vk(
            "token",
            "123",
            "Заголовок",
            "<p>Текст</p>",
            "технологии",
            image_url="https://images.example/cover.jpg",
            random_id=123456,
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 43)
        self.assertEqual(post.call_count, 2)
        self.assertNotIn("attachments", post.call_args.kwargs["data"])
        self.assertEqual(post.call_args.kwargs["data"]["random_id"], 123456)

    @patch("src.vk_publisher.requests.post")
    def test_uses_article_page_as_visual_link_card(self, post):
        post.return_value = _vk_response({"response": {"post_id": 44}})
        article_url = "https://slepoybog.github.io/Farm/article.html"

        ok, post_id = publish_to_vk(
            "token", "123", "Заголовок", "<p>Текст</p>", "технологии",
            raw_text="Полный текст",
            image_url="https://images.example/cover.jpg",
            article_url=article_url,
            random_id=1003,
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 44)
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["attachments"], article_url)
        self.assertIn(article_url, sent["message"])


if __name__ == "__main__":
    unittest.main()
