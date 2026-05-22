"""
Batch worker for AI Content Farm.
Reads topics from data/topics_queue.txt and processes them in a loop.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import process_topic, client
from src.trend_analyzer import detect_trending_niche

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/batch_worker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


def read_queue() -> list[str]:
    """Read topics from queue file."""
    queue_path = Path("data") / "topics_queue.txt"
    if not queue_path.exists():
        return []

    topics = queue_path.read_text(encoding="utf-8").strip().split("\n")
    return [t.strip() for t in topics if t.strip()]


def remove_from_queue(topic: str):
    """Remove a processed topic from the queue file."""
    queue_path = Path("data") / "topics_queue.txt"
    if not queue_path.exists():
        return

    topics = read_queue()
    topics = [t for t in topics if t != topic]
    queue_path.write_text("\n".join(topics), encoding="utf-8")
    logger.info(f"Removed '{topic}' from queue. {len(topics)} topics remaining.")


async def worker_loop():
    """Main worker loop - processes topics from queue."""
    niche = await detect_trending_niche(client)
    logger.info("=" * 60)
    logger.info("Batch Worker Started")
    logger.info(f"Niche: {niche}")
    logger.info("=" * 60)

    semaphore = asyncio.Semaphore(2)  # Process 2 topics concurrently

    while True:
        try:
            topics = read_queue()
            if not topics:
                logger.info("Queue is empty. Sleeping for 60 seconds...")
                await asyncio.sleep(60)
                continue

            logger.info(f"Found {len(topics)} topics in queue")

            # Process first topic from queue
            topic = topics[0]
            logger.info(f"Processing topic from queue: {topic}")

            await process_topic(topic, niche, semaphore)

            # Remove processed topic from queue
            remove_from_queue(topic)

            # Small delay between topics
            await asyncio.sleep(2)

        except KeyboardInterrupt:
            logger.info("Batch worker stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
            await asyncio.sleep(10)


def main():
    """Entry point for batch worker."""
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Batch worker terminated.")


if __name__ == "__main__":
    main()
