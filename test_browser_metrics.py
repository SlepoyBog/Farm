import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_vk_browser_metrics import import_metrics


class BrowserMetricsImportTests(unittest.TestCase):
    def test_imports_metrics_by_owner_and_post_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = root / "metrics.json"
            history = root / "history.json"
            metrics.write_text(
                json.dumps(
                    {
                        "collected_at": "2026-07-24T19:00:00+05:00",
                        "posts": [
                            {
                                "owner_id": "-123",
                                "post_id": 7,
                                "reach": 4,
                                "views": 13,
                                "likes": 1,
                                "comments": 2,
                                "reposts": 3,
                                "bookmarks": 4,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    [
                        {
                            "platforms": {
                                "vk": {
                                    "owner_id": "-123",
                                    "post_id": 7,
                                    "views": None,
                                }
                            }
                        }
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(import_metrics(metrics, history), (1, 1))
            stored = json.loads(history.read_text(encoding="utf-8"))
            vk = stored[0]["platforms"]["vk"]
            self.assertEqual(vk["views"], 13)
            self.assertEqual(vk["metric_snapshots"]["latest"]["source"], "vk_browser")


if __name__ == "__main__":
    unittest.main()
