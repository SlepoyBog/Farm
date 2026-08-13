"""Publish queued VK posts after GitHub Pages has deployed their link cards."""

import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.vk_pending import load_pending, save_pending
from src.vk_publisher import publish_to_vk


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
HISTORY_PATH = Path("data") / "post_history.json"


def _page_is_ready(url: str, attempts: int = 8, delay: int = 5) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=20)
            html = response.text.lower()
            image_match = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                response.text,
                flags=re.IGNORECASE,
            )
            if response.ok and image_match and image_match.group(1).strip() and 'property="og:title"' in html:
                return True
            logger.info("VK card page not ready yet (%s, attempt %d)", response.status_code, attempt)
        except requests.RequestException as exc:
            logger.warning("VK card readiness check failed (attempt %d): %s", attempt, exc)
        if attempt < attempts:
            time.sleep(delay)
    return False


def _record_vk_post(item: dict, post_id: int, group_id: str) -> bool:
    from src.state_store import atomic_write_json, read_json
    history = read_json(HISTORY_PATH, [], critical=True)
    if not isinstance(history, list):
        return False

    numeric_id = str(group_id).removeprefix("club").removeprefix("public")
    publication_id = str(item.get("publication_id") or "")
    title = str(item.get("title") or "")
    candidates = [r for r in history if publication_id and r.get("publication_id") == publication_id]
    if not candidates:
        legacy = [r for r in history if r.get("title") == title and "vk" not in r.get("platforms", {})]
        candidates = legacy if len(legacy) == 1 else []
    if not candidates and publication_id:
        record = {
            "publication_id": publication_id,
            "topic": item.get("title", ""),
            "title": title,
            "niche": item.get("niche", ""),
            "published_at": item.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "platforms": {},
            "score": None,
        }
        history.append(record)
        candidates = [record]
    for record in reversed(candidates):
        if "vk" not in record.get("platforms", {}):
            record.setdefault("platforms", {})["vk"] = {
                "post_id": post_id,
                "owner_id": f"-{numeric_id}",
                "format": "link_card",
                "views": None,
                "likes": None,
                "comments": None,
                "reposts": None,
            }
            atomic_write_json(HISTORY_PATH, history)
            return True
        if record.get("platforms", {}).get("vk", {}).get("post_id") == post_id:
            return True
    return False


def _record_telegram_post(item: dict, message_id: int) -> bool:
    from src.state_store import atomic_write_json, read_json
    history = read_json(HISTORY_PATH, [], critical=True)
    if not isinstance(history, list):
        return False
    publication_id = str(item.get("publication_id") or "")
    candidates = [r for r in history if publication_id and r.get("publication_id") == publication_id]
    for record in reversed(candidates):
        platform = record.setdefault("platforms", {}).setdefault("telegram", {})
        platform.update({"message_id": message_id, "views": None, "reactions": None})
        atomic_write_json(HISTORY_PATH, history)
        return True
    return False


def main() -> None:
    token = os.getenv("VK_ACCESS_TOKEN", "")
    group_id = os.getenv("VK_GROUP_ID", "")
    pending = load_pending()
    if not pending:
        logger.info("No deferred VK posts to publish")
        return

    failed = []
    for item in pending:
        article_url = item.get("article_url", "")
        if not article_url or not _page_is_ready(article_url):
            logger.error("VK link card page is unavailable: %s", article_url)
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["last_error"] = "VK link card page is unavailable"
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            failed.append(item)
            continue

        telegram_message_id = item.get("telegram_message_id")
        if not telegram_message_id:
            from src.main import publish_to_telegram
            tg_ok, telegram_message_id = publish_to_telegram(
                title=item.get("title", ""),
                html_content=item.get("telegram_html_content") or item.get("html_content", ""),
                image_url=item.get("telegram_image_url"),
                article_url=article_url,
                niche=item.get("niche", ""),
            )
            if not tg_ok or telegram_message_id is None:
                item["attempts"] = int(item.get("attempts") or 0) + 1
                item["last_error"] = "Telegram publication failed"
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                failed.append(item)
                continue
            item["telegram_message_id"] = telegram_message_id
            _record_telegram_post(item, telegram_message_id)
            # Persist immediately: a later VK error must not cause Telegram to
            # publish the same item again on the next workflow retry.
            save_pending(pending)

        ok, post_id = publish_to_vk(
            access_token=token,
            group_id=group_id,
            title=item.get("title", ""),
            html_content=item.get("html_content", ""),
            niche=item.get("niche", ""),
            raw_text=item.get("raw_text", ""),
            article_url=article_url,
            random_id=item.get("vk_random_id"),
        )
        if ok and post_id is not None:
            if not _record_vk_post(item, post_id, group_id):
                item["last_error"] = "VK post sent but history update failed"
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                failed.append(item)
        else:
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["last_error"] = "VK publication failed"
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            failed.append(item)

    save_pending(failed)
    if failed:
        raise SystemExit(f"Failed to publish {len(failed)} deferred VK post(s)")


if __name__ == "__main__":
    main()
