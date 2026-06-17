import json
import logging
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TARGETS_PATH = Path("data") / "cross_post_targets.json"


def _load_targets() -> list[dict]:
    if TARGETS_PATH.exists():
        try:
            return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return []
    return []


def _save_targets(targets: list[dict]):
    TARGETS_PATH.write_text(
        json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_target(name: str, chat_id: str, platform: str = "telegram"):
    targets = _load_targets()
    for t in targets:
        if t["chat_id"] == chat_id:
            logger.info("Target %s already exists", chat_id)
            return
    targets.append({"name": name, "chat_id": chat_id, "platform": platform, "active": True})
    _save_targets(targets)
    logger.info("Added cross-post target: %s (%s)", name, chat_id)


def _extract_announcement(article_text: str, max_chars: int = 300) -> str:
    text = re.sub(r"<[^>]+>", "", article_text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars // 2:
        cut = cut[:last_space]
    return cut + "..."


def post_to_channel(
    bot_token: str,
    target_chat_id: str,
    announcement: str,
    article_title: str = "",
    site_url: str = "",
) -> bool:
    text = announcement
    if article_title:
        text = f"{article_title}\n\n{announcement}"
    if site_url:
        text += f"\n\nЧитать полностью: {site_url}"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": target_chat_id,
                "text": text[:4000],
                "parse_mode": "HTML",
            },
            timeout=30,
        )
        if resp.ok:
            logger.info(f"Cross-post sent to {target_chat_id}")
            return True
        logger.warning(f"Cross-post to {target_chat_id} failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Cross-post error to {target_chat_id}: {e}")
    return False


def run_cross_post(announcement: str, title: str = "", site_url: str = ""):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping cross-post")
        return

    targets = _load_targets()
    if not targets:
        logger.info("No cross-post targets configured. Add via data/cross_post_targets.json")
        return

    success = 0
    for target in targets:
        if not target.get("active", True):
            continue
        if target.get("platform") != "telegram":
            continue
        if post_to_channel(bot_token, target["chat_id"], announcement, title, site_url):
            success += 1

    logger.info(f"Cross-post: {success}/{len(targets)} targets successful")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

    if len(sys.argv) >= 4 and sys.argv[1] == "--add":
        add_target(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "telegram")
    elif len(sys.argv) >= 3:
        run_cross_post(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        print("Usage:")
        print("  python growth/cross_poster.py --add <name> <chat_id> [platform]")
        print("  python growth/cross_poster.py <announcement> [title]")
