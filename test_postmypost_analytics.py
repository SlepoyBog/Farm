import json
import tempfile
import unittest
from pathlib import Path

from src.postmypost_analytics import import_into_history, normalize_publication


class PostmypostAnalyticsTests(unittest.TestCase):
    def test_normalizes_nested_metrics_and_vk_url(self):
        result = normalize_publication(
            {
                "publication": {
                    "id": "pub-1",
                    "text": "Полный текст публикации",
                    "url": "https://vk.ru/wall-186888784_700",
                    "published_at": "2026-07-26T10:00:00+05:00",
                },
                "analytics": {
                    "actions": 2,
                    "reactions": 3,
                    "comments": 4,
                    "views": 20,
                    "reach": 15,
                    "err": "9,5 %",
                    "erv": "7.1",
                },
            }
        )
        self.assertEqual(result["post_id"], 700)
        self.assertEqual(result["views"], 20)
        self.assertEqual(result["reactions"], 3)
        self.assertEqual(result["err"], 9.5)

    def test_imports_by_vk_post_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            history_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "Тест",
                            "platforms": {
                                "vk": {"owner_id": "-186888784", "post_id": 700}
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            metrics = [
                {
                    "post_id": 700,
                    "text": "Тест",
                    "views": 20,
                    "reach": 15,
                    "reactions": 3,
                    "comments": 4,
                    "actions": 2,
                    "err": 9.5,
                    "erv": 7.1,
                }
            ]
            self.assertEqual(
                import_into_history(
                    metrics,
                    history_path=history_path,
                    collected_at="2026-07-26T12:00:00Z",
                ),
                (1, 1),
            )
            stored = json.loads(history_path.read_text(encoding="utf-8"))
            vk = stored[0]["platforms"]["vk"]
            self.assertEqual(vk["views"], 20)
            self.assertEqual(
                vk["metric_snapshots"]["latest"]["source"],
                "postmypost_api",
            )

    def test_imports_by_title_when_post_id_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            history_path.write_text(
                json.dumps(
                    [
                        {
                            "title": "Как ускорить загрузку сайта",
                            "platforms": {"vk": {}},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            metrics = [
                {
                    "post_id": None,
                    "text": "Как ускорить загрузку сайта — пять понятных шагов",
                    "views": 8,
                    "reach": 7,
                    "reactions": 1,
                    "comments": 0,
                    "actions": 0,
                    "err": 0.0,
                    "erv": 0.0,
                }
            ]
            self.assertEqual(
                import_into_history(metrics, history_path=history_path),
                (1, 1),
            )


if __name__ == "__main__":
    unittest.main()
