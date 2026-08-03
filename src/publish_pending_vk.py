"""Publish queued VK posts after GitHub Pages has deployed their link cards."""

import json
import logging
import os
import time
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
            if response.ok and 'property="og:image"' in html and 'property="og:title"' in html:
                return True
            logger.info("VK card page not ready yet (%s, attempt %d)", response.status_code, attempt)
        except requests.RequestException as exc:
            logger.warning("VK card readiness check failed (attempt %d): %s", attempt, exc)
        if attempt < attempts:
            time.sleep(delay)
    return False


def _record_vk_post(title: str, post_id: int, group_id: str) -> None:
    if not HISTORY_PATH.exists():
        return
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    numeric_id = str(group_id).removeprefix("club").removeprefix("public")
    for record in reversed(history):
        if record.get("title") == title and "vk" not in record.get("platforms", {}):
            record.setdefault("platforms", {})["vk"] = {
                "post_id": post_id,
                "owner_id": f"-{numeric_id}",
                "format": "link_card",
                "views": None,
                "likes": None,
                "comments": None,
                "reposts": None,
            }
            HISTORY_PATH.write_text(
                json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return


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
            failed.append(item)
            continue

        ok, post_id = publish_to_vk(
            access_token=token,
            group_id=group_id,
            title=item.get("title", ""),
            html_content=item.get("html_content", ""),
            niche=item.get("niche", ""),
            raw_text=item.get("raw_text", ""),
            article_url=article_url,
        )
        if ok and post_id is not None:
            _record_vk_post(item.get("title", ""), post_id, group_id)
        else:
            failed.append(item)

    save_pending(failed)
    if failed:
        raise SystemExit(f"Failed to publish {len(failed)} deferred VK post(s)")


if __name__ == "__main__":
    main()
