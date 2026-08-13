"""Queue VK posts until their Open Graph pages are deployed."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from src.state_store import atomic_write_json, read_json


PENDING_PATH = Path("data") / "pending_vk.json"


def load_pending() -> list[dict]:
    data = read_json(PENDING_PATH, [], critical=True)
    if not isinstance(data, list):
        from src.state_store import StateCorruptionError
        raise StateCorruptionError(f"Expected a JSON list in {PENDING_PATH}")
    migrated = []
    changed = False
    for original in data:
        if not isinstance(original, dict):
            from src.state_store import StateCorruptionError
            raise StateCorruptionError(f"Invalid queue item in {PENDING_PATH}")
        item = dict(original)
        if not item.get("publication_id"):
            identity = str(item.get("article_url") or item.get("title") or uuid4())
            item["publication_id"] = str(uuid5(NAMESPACE_URL, identity))
            changed = True
        if not item.get("vk_random_id"):
            item["vk_random_id"] = stable_vk_random_id(item["publication_id"])
            changed = True
        if item.get("schema_version") != 2:
            item["schema_version"] = 2
            item.setdefault("status", "queued")
            item.setdefault("attempts", 0)
            item.setdefault("last_error", None)
            changed = True
        migrated.append(item)
    if changed:
        save_pending(migrated)
    return migrated


def save_pending(items: list[dict]) -> None:
    atomic_write_json(PENDING_PATH, items)


def stable_vk_random_id(publication_id: str) -> int:
    value = int.from_bytes(hashlib.sha256(publication_id.encode("utf-8")).digest()[:4], "big")
    return (value & 0x7FFFFFFF) or 1


def queue_vk_post(item: dict) -> None:
    items = load_pending()
    now = datetime.now(timezone.utc).isoformat()
    publication_id = str(item.get("publication_id") or uuid4())
    item = {
        **item,
        "schema_version": 2,
        "publication_id": publication_id,
        "vk_random_id": int(item.get("vk_random_id") or stable_vk_random_id(publication_id)),
        "status": "queued",
        "attempts": int(item.get("attempts") or 0),
        "last_error": item.get("last_error"),
        "created_at": item.get("created_at") or now,
        "updated_at": now,
    }
    article_url = item.get("article_url")
    items = [
        queued for queued in items
        if queued.get("publication_id") != publication_id
        and (not article_url or queued.get("article_url") != article_url)
    ]
    items.append(item)
    save_pending(items)
