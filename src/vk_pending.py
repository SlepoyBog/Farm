"""Queue VK posts until their Open Graph pages are deployed."""

import json
from pathlib import Path


PENDING_PATH = Path("data") / "pending_vk.json"


def load_pending() -> list[dict]:
    if not PENDING_PATH.exists():
        return []
    try:
        data = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_pending(items: list[dict]) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def queue_vk_post(item: dict) -> None:
    items = load_pending()
    article_url = item.get("article_url")
    items = [queued for queued in items if queued.get("article_url") != article_url]
    items.append(item)
    save_pending(items)
