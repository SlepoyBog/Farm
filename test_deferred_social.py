import unittest
from unittest.mock import Mock, patch

from src import publish_pending_vk


class DeferredSocialTests(unittest.TestCase):
    @patch("src.publish_pending_vk.time.sleep")
    @patch("src.publish_pending_vk.requests.get")
    def test_page_ready_requires_nonempty_open_graph_image(self, get, _sleep):
        get.return_value = Mock(
            ok=True,
            status_code=200,
            text='<meta property="og:title" content="Title"><meta property="og:image" content="">',
        )
        self.assertFalse(publish_pending_vk._page_is_ready("https://example.com", attempts=1))

    @patch("src.publish_pending_vk.requests.get")
    def test_page_ready_accepts_open_graph_image(self, get):
        get.return_value = Mock(
            ok=True,
            status_code=200,
            text=(
                '<meta property="og:title" content="Title">'
                '<meta property="og:image" content="https://example.com/image.jpg">'
            ),
        )
        self.assertTrue(publish_pending_vk._page_is_ready("https://example.com", attempts=1))


if __name__ == "__main__":
    unittest.main()
