"""Backfill image_url into all existing .meta.json files that lack it."""
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")

meta_files = sorted(OUTPUT_DIR.glob("*.meta.json"))
logger.info(f"Found {len(meta_files)} meta files")

fixed = 0
skipped = 0
rate_limited = False

for mpath in meta_files:
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception:
        continue

    if data.get("image_url"):
        skipped += 1
        continue

    niche = data.get("niche") or "технологии"
    slug = data.get("slug") or mpath.stem

    from src.image_provider import get_image_url
    url = get_image_url(niche, slug)
    if url:
        data["image_url"] = url
        mpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        fixed += 1
        logger.info(f"[{fixed}] Added image to {mpath.name}")
        time.sleep(0.5)
    else:
        logger.warning(f"No image for {mpath.name} (niche={niche})")

logger.info(f"Done: {fixed} fixed, {skipped} already had images")
