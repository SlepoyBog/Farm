import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.main import (
    _choose_ab_variant,
    _deduplicate_topics,
    _parse_topic_list,
    _recent_topic_titles,
)


class TopicGenerationTests(unittest.TestCase):
    def test_parser_removes_common_list_markers(self):
        result = _parse_topic_list("- 🧠 Первая тема\n2. 🚗 Вторая тема\n• 💰 Третья тема")
        self.assertEqual(
            result,
            ["🧠 Первая тема", "🚗 Вторая тема", "💰 Третья тема"],
        )

    def test_removes_duplicates_and_close_paraphrases(self):
        result = _deduplicate_topics(
            [
                "🚗 Как выбрать автомобиль с пробегом",
                "🚙 Как выбрать автомобиль с пробегом без ошибок",
                "💰 Как сократить расходы на продукты",
            ]
        )
        self.assertEqual(
            result,
            [
                "🚗 Как выбрать автомобиль с пробегом",
                "💰 Как сократить расходы на продукты",
            ],
        )

    def test_excludes_recently_published_topic(self):
        result = _deduplicate_topics(
            ["🧠 Как улучшить качество сна", "🏃 Как начать бегать"],
            excluded=["Как улучшить качество сна без лекарств"],
        )
        self.assertEqual(result, ["🏃 Как начать бегать"])

    @patch("src.main.POST_HISTORY_PATH")
    def test_recent_titles_tolerates_missing_history(self, history_path):
        history_path.exists.return_value = False
        self.assertEqual(_recent_topic_titles(), [])

    def test_ab_variants_start_balanced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.json"
            history_path.write_text(
                json.dumps([{"ab_variant": "A"}]),
                encoding="utf-8",
            )
            self.assertEqual(_choose_ab_variant(history_path), "B")

    def test_ab_variant_favors_winner_after_enough_samples(self):
        records = []
        for variant, views in (("A", 40), ("B", 10)):
            for _ in range(20):
                records.append(
                    {
                        "ab_variant": variant,
                        "platforms": {"vk": {"views": views}},
                    }
                )
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.json"
            history_path.write_text(json.dumps(records), encoding="utf-8")
            self.assertEqual(_choose_ab_variant(history_path), "A")

    def test_ab_does_not_pick_winner_from_small_sample(self):
        records = []
        for variant, views in (("A", 100), ("B", 1)):
            for _ in range(5):
                records.append({"ab_variant": variant, "platforms": {"vk": {"views": views}}})
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.json"
            history_path.write_text(json.dumps(records), encoding="utf-8")
            self.assertEqual(_choose_ab_variant(history_path), "A")


if __name__ == "__main__":
    unittest.main()
