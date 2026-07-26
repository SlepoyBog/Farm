import unittest
from unittest.mock import patch

from src.main import _deduplicate_topics, _parse_topic_list, _recent_topic_titles


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


if __name__ == "__main__":
    unittest.main()
