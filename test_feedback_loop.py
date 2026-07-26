import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src import feedback_loop


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FeedbackLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "post_history.json"
        self.path_patch = patch.object(
            feedback_loop, "POST_HISTORY_PATH", self.history_path
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def record(post_id=42, hours_old=25):
        return {
            "topic": "Тема",
            "title": "Заголовок",
            "niche": "технологии",
            "published_at": (
                datetime.now() - timedelta(hours=hours_old)
            ).isoformat(),
            "platforms": {
                "vk": {
                    "post_id": post_id,
                    "owner_id": "-123",
                    "views": None,
                    "likes": None,
                    "comments": None,
                    "reposts": None,
                }
            },
            "score": None,
        }

    def test_fetches_exact_saved_vk_reference(self):
        history = [self.record()]
        calls = []

        def fake_post(url, data, timeout):
            calls.append((url, data, timeout))
            return FakeResponse(
                {
                    "response": [
                        {
                            "id": 42,
                            "owner_id": -123,
                            "views": {"count": 150},
                            "likes": {"count": 7},
                            "comments": {"count": 2},
                            "reposts": {"count": 1},
                        }
                    ]
                }
            )

        metrics = feedback_loop._fetch_vk_metrics(
            history, "token", "123", fake_post
        )

        self.assertIn("-123_42", metrics)
        self.assertEqual(calls[0][1]["posts"], "-123_42")
        self.assertIn("wall.getById", calls[0][0])

    def test_group_token_error_returns_no_fake_metrics(self):
        history = [self.record()]

        def fake_post(url, data, timeout):
            return FakeResponse(
                {
                    "error": {
                        "error_code": 27,
                        "error_msg": "Group authorization failed",
                    }
                }
            )

        with self.assertLogs(feedback_loop.logger, level="ERROR") as logs:
            metrics = feedback_loop._fetch_vk_metrics(
                history, "group-token", "123", fake_post
            )

        self.assertEqual(metrics, {})
        self.assertIn("VK_ANALYTICS_TOKEN", "\n".join(logs.output))

    def test_applies_metrics_and_creates_24h_snapshot(self):
        history = [self.record(hours_old=25)]
        matched, changed = feedback_loop._apply_vk_metrics(
            history,
            {
                "-123_42": {
                    "views": 150,
                    "likes": 7,
                    "comments": 2,
                    "reposts": 1,
                }
            },
            "-123",
        )

        vk = history[0]["platforms"]["vk"]
        self.assertEqual((matched, changed), (1, 1))
        self.assertEqual(vk["views"], 150)
        self.assertIn("24h", vk["metric_snapshots"])
        self.assertIn("latest", vk["metric_snapshots"])

    def test_collect_metrics_persists_matches(self):
        feedback_loop._save_history([self.record()])

        def fake_post(url, data, timeout):
            return FakeResponse(
                {
                    "response": [
                        {
                            "id": 42,
                            "owner_id": -123,
                            "views": {"count": 99},
                            "likes": {"count": 3},
                            "comments": {"count": 1},
                            "reposts": {"count": 0},
                        }
                    ]
                }
            )

        with patch("requests.post", side_effect=fake_post):
            asyncio.run(feedback_loop.collect_metrics("token", "123"))

        stored = feedback_loop._load_history()
        self.assertEqual(stored[0]["platforms"]["vk"]["views"], 99)

    def test_unmeasured_posts_are_not_scored(self):
        history = [self.record()]
        scored = feedback_loop.score_posts(history=history)
        self.assertEqual(scored, [])
        self.assertIsNone(history[0]["score"])


if __name__ == "__main__":
    unittest.main()
