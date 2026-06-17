import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

HISTORY_PATH = Path("data") / "subscriber_history.json"


def _load_history() -> list[dict]:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return []
    return []


def _save_history(history: list[dict]):
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def track_telegram(bot_token: str, chat_id: str) -> int | None:
    if not bot_token or not chat_id:
        logger.warning("Telegram not configured for tracking")
        return None
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getChatMemberCount",
            params={"chat_id": chat_id},
            timeout=15,
        )
        if resp.ok:
            count = resp.json().get("result")
            logger.info(f"TG subscribers: {count}")
            return count
        logger.warning(f"TG tracking failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"TG tracking error: {e}")
    return None


def track_vk(access_token: str, group_id: str) -> int | None:
    if not access_token or not group_id:
        logger.warning("VK not configured for tracking")
        return None
    numeric_id = group_id
    if numeric_id.startswith("club"):
        numeric_id = numeric_id[4:]
    if numeric_id.startswith("public"):
        numeric_id = numeric_id[6:]
    try:
        resp = requests.get(
            "https://api.vk.com/method/groups.getById",
            params={
                "group_id": numeric_id,
                "fields": "members_count",
                "access_token": access_token,
                "v": "5.199",
            },
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            if "response" in data and len(data["response"]) > 0:
                count = data["response"][0].get("members_count")
                logger.info(f"VK subscribers: {count}")
                return count
        logger.warning(f"VK tracking failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"VK tracking error: {e}")
    return None


def run_tracker() -> dict:
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    vk_token = os.getenv("VK_ACCESS_TOKEN", "")
    vk_group = os.getenv("VK_GROUP_ID", "")

    tg_count = track_telegram(tg_token, tg_chat)
    vk_count = track_vk(vk_token, vk_group)

    snapshot = {
        "date": datetime.now().isoformat(),
        "telegram": tg_count,
        "vk": vk_count,
    }

    history = _load_history()
    history.append(snapshot)
    _save_history(history)

    logger.info(f"Subscriber snapshot saved: TG={tg_count}, VK={vk_count}")
    return snapshot


def get_growth_summary(days: int = 30) -> str:
    history = _load_history()
    if not history:
        return "Нет данных по подписчикам."

    recent = [h for h in history
              if (datetime.now() - datetime.fromisoformat(h["date"])).days <= days]

    if not recent:
        return "Нет данных за последние %d дней." % days

    first = recent[0]
    last = recent[-1]

    tg_start = first.get("telegram") or 0
    tg_end = last.get("telegram") or 0
    vk_start = first.get("vk") or 0
    vk_end = last.get("vk") or 0

    lines = [
        "📊 Рост подписчиков за %d дней:" % days,
        "",
        f"  Telegram: {tg_start} → {tg_end} ({tg_end - tg_start:+d})",
        f"  VK:       {vk_start} → {vk_end} ({vk_end - vk_start:+d})",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    if "--summary" in sys.argv:
        print(get_growth_summary())
    else:
        run_tracker()
