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
    def test_skips_direct_publish_when_rss_mode_is_enabled(self, post):
        ok, post_id = publish_to_vk(
            "token",
            "club123",
            "Заголовок",
            "<p>Текст</p>",
            "технологии",
        )

        self.assertFalse(ok)
        self.assertIsNone(post_id)
        post.assert_not_called()

    @patch("src.vk_publisher.requests.post")
    @patch("src.vk_publisher._upload_wall_photo", return_value=None)
    def test_uses_image_url_when_group_token_cannot_upload_photo(self, _, post):
        post.return_value = _vk_response({"response": {"post_id": 42}})

        ok, post_id = publish_to_vk(
            "token",
            "club123",
            "Заголовок",
            "<p>Текст</p>",
            "технологии",
            image_url="https://images.example/cover.jpg",
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 42)
        self.assertEqual(
            post.call_args.kwargs["data"]["attachments"],
            "https://images.example/cover.jpg",
        )

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
        )

        self.assertTrue(ok)
        self.assertEqual(post_id, 43)
        self.assertEqual(post.call_count, 2)
        self.assertNotIn("attachments", post.call_args.kwargs["data"])


if __name__ == "__main__":
    unittest.main()
