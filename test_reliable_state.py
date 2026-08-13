import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import vk_pending
from src.state_store import StateCorruptionError, atomic_write_json, read_json


class ReliableStateTests(unittest.TestCase):
    def test_atomic_write_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"ok": True})
            self.assertEqual(read_json(path, {}), {"ok": True})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_failed_replace_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{"old": true}', encoding="utf-8")
            with patch("src.state_store.os.replace", side_effect=OSError("stop")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"old": True})

    def test_corrupt_critical_state_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(StateCorruptionError):
                read_json(path, [], critical=True)

    def test_queued_post_keeps_stable_random_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending.json"
            with patch.object(vk_pending, "PENDING_PATH", path):
                vk_pending.queue_vk_post({"publication_id": "pub-1", "article_url": "https://example/1"})
                first = vk_pending.load_pending()[0]
                vk_pending.queue_vk_post({"publication_id": "pub-1", "article_url": "https://example/1"})
                second = vk_pending.load_pending()[0]
            self.assertEqual(first["vk_random_id"], second["vk_random_id"])
            self.assertGreater(first["vk_random_id"], 0)

    def test_legacy_queue_is_migrated_before_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending.json"
            path.write_text(json.dumps([{"title": "Legacy", "article_url": "https://example/old"}]), encoding="utf-8")
            with patch.object(vk_pending, "PENDING_PATH", path):
                item = vk_pending.load_pending()[0]
            self.assertEqual(item["schema_version"], 2)
            self.assertTrue(item["publication_id"])
            self.assertGreater(item["vk_random_id"], 0)

    def test_same_article_replaces_older_pending_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending.json"
            with patch.object(vk_pending, "PENDING_PATH", path):
                vk_pending.queue_vk_post({"publication_id": "one", "article_url": "https://example/same"})
                vk_pending.queue_vk_post({"publication_id": "two", "article_url": "https://example/same"})
                items = vk_pending.load_pending()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["publication_id"], "two")


if __name__ == "__main__":
    unittest.main()
