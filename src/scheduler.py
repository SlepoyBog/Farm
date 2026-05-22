import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.feedback_loop import record_publication
from src.main import generate_topics, process_topic, client
from src.trend_analyzer import detect_trending_niche
from src.vk_publisher import publish_to_vk

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

load_dotenv()

VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "")

STATE_PATH = Path("data") / "schedule_state.json"
QUEUE_PATH = Path("data") / "topics_queue.txt"


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return {}
    return {}


def _save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _today_published() -> bool:
    state = _load_state()
    last_date = state.get("last_publish_date")
    return last_date == date.today().isoformat()


def _mark_published(niche: str = ""):
    state = _load_state()
    state["last_publish_date"] = date.today().isoformat()
    state["last_publish_time"] = datetime.now().strftime("%H:%M:%S")
    if niche:
        state["last_niche"] = niche
    _save_state(state)


def _read_queue() -> list[str]:
    if not QUEUE_PATH.exists():
        return []
    topics = QUEUE_PATH.read_text(encoding="utf-8").strip().split("\n")
    return [t.strip() for t in topics if t.strip()]


def _remove_from_queue(topic: str):
    topics = _read_queue()
    topics = [t for t in topics if t != topic]
    QUEUE_PATH.write_text("\n".join(topics), encoding="utf-8")


async def run_once(force_niche: str = ""):
    if _today_published() and not force_niche:
        logger.info("Today's post already published. Skipping.")
        return

    niche = force_niche or await detect_trending_niche(client)

    logger.info("=" * 60)
    logger.info(f"Daily Scheduler — {date.today().isoformat()}")
    logger.info(f"Trending niche: {niche}")
    logger.info("=" * 60)

    queue = _read_queue()

    if queue:
        topic = queue[0]
        logger.info(f"Taking topic from queue: {topic}")
        _remove_from_queue(topic)
    else:
        logger.info("Queue is empty. Generating new topics...")
        topics = await generate_topics(niche)
        if not topics:
            logger.error("Failed to generate topics.")
            return
        topic = topics[0]
        remaining = topics[1:]
        if remaining:
            QUEUE_PATH.write_text("\n".join(remaining), encoding="utf-8")
            logger.info(f"Saved {len(remaining)} topics to queue for later")

    semaphore = asyncio.Semaphore(1)
    result = await process_topic(topic, niche, semaphore)

    if result is not None:
        _mark_published(niche)
        logger.info(f"Daily post published successfully. Topic: {topic} | Niche: {niche}")
    else:
        logger.error(f"Failed to process topic: {topic}")


async def _flush_queue(force_niche: str = ""):
    niche = force_niche or await detect_trending_niche(client)
    logger.info(f"Flush mode — processing all queued topics. Niche: {niche}")

    queue = _read_queue()
    if not queue:
        logger.info("Queue is empty. Generating fresh topics...")
        topics = await generate_topics(niche)
        if not topics:
            logger.error("Failed to generate topics.")
            return
        queue = topics

    semaphore = asyncio.Semaphore(2)
    results = []
    for topic in queue:
        logger.info(f"Flush processing: {topic}")
        result = await process_topic(topic, niche, semaphore)
        if result is not None:
            results.append((result[0], result[2], niche))
            _remove_from_queue(topic)

    vk_items = [(r[0], r[1]) for r in results]
    if vk_items:
        from src.vk_publisher import combine_for_vk
        combined = combine_for_vk(vk_items, niche)
        ok, post_id = publish_to_vk(
            VK_ACCESS_TOKEN, VK_GROUP_ID, "Дайджест", "", niche, raw_text=combined
        )
        if ok and post_id:
            vk_num = VK_GROUP_ID
            if vk_num.startswith("club"):
                vk_num = vk_num[4:]
            if vk_num.startswith("public"):
                vk_num = vk_num[6:]
            record_publication(
                topic="Дайджест",
                title="Дайджест",
                niche=niche,
                vk_post_id=post_id,
                vk_owner_id=f"-{vk_num}",
            )

    if results:
        _mark_published(niche)
    logger.info(f"Flush complete. Published {len(results)} posts.")


def _publish_vk(title: str, vk_text: str, niche: str = ""):
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        logger.warning("VK not configured. Skipping VK post.")
        return
    try:
        ok, post_id = publish_to_vk(
            access_token=VK_ACCESS_TOKEN,
            group_id=VK_GROUP_ID,
            title=title,
            html_content="",
            niche=niche,
            raw_text=vk_text,
        )
        if ok and post_id:
            numeric_id = VK_GROUP_ID
            if numeric_id.startswith("club"):
                numeric_id = numeric_id[4:]
            if numeric_id.startswith("public"):
                numeric_id = numeric_id[6:]
            record_publication(
                topic=title,
                title=title,
                niche=niche,
                vk_post_id=post_id,
                vk_owner_id=f"-{numeric_id}",
            )
    except Exception as e:
        logger.error(f"VK publish failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="AI Content Farm — Daily Scheduler")
    parser.add_argument(
        "--time", "-t",
        type=str,
        default=None,
        help="Set daily publish time (HH:MM format)",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show schedule status",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for Task Scheduler)",
    )
    parser.add_argument(
        "--niche", "-n",
        type=str,
        default=None,
        help="Force specific niche (skip trend analysis)",
    )
    parser.add_argument(
        "--flush", "-f",
        action="store_true",
        help="Process all topics in queue immediately",
    )
    args = parser.parse_args()

    if args.time:
        state = _load_state()
        state["publish_time"] = args.time
        _save_state(state)
        logger.info(f"Daily publish time set to {args.time}")
        return

    if args.status:
        state = _load_state()
        last_date = state.get("last_publish_date", "never")
        last_niche = state.get("last_niche", "-")
        pub_time = state.get("publish_time", "10:00")
        logger.info(f"Schedule status:")
        logger.info(f"  Publish time: {pub_time}")
        logger.info(f"  Last post: {last_date}")
        logger.info(f"  Last niche: {last_niche}")
        logger.info(f"  Today published: {_today_published()}")
        queue = _read_queue()
        logger.info(f"  Topics in queue: {len(queue)}")
        return

    if args.flush:
        asyncio.run(_flush_queue(force_niche=args.niche or ""))
        return

    asyncio.run(run_once(force_niche=args.niche or ""))


if __name__ == "__main__":
    main()
