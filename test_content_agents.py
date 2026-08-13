import json
import unittest
from unittest.mock import AsyncMock

from src.content_agents import active_agent_names, run_editorial_board


class ContentAgentsTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_contains_critical_roles(self):
        names = active_agent_names()
        self.assertIn("Фактчекер", names)
        self.assertIn("Редактор безопасности", names)
        self.assertIn("Аналитик роста", names)

    async def test_editorial_board_normalizes_result(self):
        client = AsyncMock()
        client.call_json.return_value = {
            "approved": False,
            "score": 5,
            "issues": "Неподтверждённая цифра",
            "feedback": "Удалить точную цифру",
        }

        def prompt_loader(_):
            return "system", "{{topic}} {{outline}} {{article}}"

        result = await run_editorial_board(
            client, prompt_loader, "Тема", ["Пункт"], "Статья"
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["issues"], ["Неподтверждённая цифра"])
        client.call_json.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
