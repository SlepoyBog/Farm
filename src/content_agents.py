"""Editorial agent registry and the pre-publication quality gate."""

import json
import logging
from pathlib import Path


logger = logging.getLogger(__name__)
REGISTRY_PATH = Path("data") / "content_agents.json"


def load_agent_registry() -> list[dict]:
    try:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Content agent registry is unavailable")
        return []
    agents = payload.get("agents", [])
    return agents if isinstance(agents, list) else []


def active_agent_names() -> list[str]:
    return [str(agent.get("name", "")).strip() for agent in load_agent_registry() if agent.get("name")]


async def run_editorial_board(client, load_prompt, topic: str, outline: list[str], article: str) -> dict:
    """Run one cost-conscious call combining editor, fact-check and safety roles."""
    system_prompt, user_template = load_prompt("editorial_board")
    user_prompt = (
        user_template.replace("{{topic}}", topic)
        .replace("{{outline}}", json.dumps(outline, ensure_ascii=False))
        .replace("{{article}}", article)
    )
    result = await client.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=1000,
    )
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        issues = [str(issues)]
    return {
        "approved": bool(result.get("approved", False)),
        "score": float(result.get("score", 0) or 0),
        "issues": [str(issue).strip() for issue in issues if str(issue).strip()],
        "feedback": str(result.get("feedback", "")).strip(),
    }
