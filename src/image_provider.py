import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

UNSPLASH_API_BASE = "https://api.unsplash.com"

NICHE_QUERIES = {
    "искусственный интеллект": ["artificial-intelligence", "robot", "neural-network", "technology"],
    "авто": ["car", "automotive", "electric-car", "engine"],
    "технологии": ["technology", "gadget", "digital", "innovation"],
    "здоровье": ["health", "medical", "wellness", "fitness"],
    "финансы": ["finance", "money", "investment", "crypto"],
    "бизнес": ["business", "startup", "office", "entrepreneur"],
    "образование": ["education", "study", "library", "learning"],
    "спорт": ["sport", "fitness", "stadium", "athlete"],
    "кино": ["cinema", "movie", "film", "popcorn"],
    "путешествия": ["travel", "vacation", "adventure", "landscape"],
}

DEFAULT_QUERIES = ["technology", "abstract", "digital"]

def _pick_query(niche: str, topic: str) -> str:
    queries = NICHE_QUERIES.get(niche, DEFAULT_QUERIES)
    idx = hash(topic) % len(queries)
    return queries[idx]


FALLBACK_URLS = [
    "https://picsum.photos/seed/{seed}/800/600",
    "https://via.placeholder.com/800x600/1a1a2e/ffffff?text=Article",
]

def get_image_url(niche: str, topic: str, orientation: str = "landscape") -> Optional[str]:

    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if access_key:
        query = _pick_query(niche, topic)
        try:
            resp = requests.get(
                f"{UNSPLASH_API_BASE}/photos/random",
                headers={"Authorization": f"Client-ID {access_key}"},
                params={"query": query, "orientation": orientation, "count": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                data = data[0]
            url = data.get("urls", {}).get("regular")
            if url:
                logger.info(f"Fetched Unsplash image | query='{query}' | niche='{niche}'")
                return url
        except Exception as e:
            logger.warning(f"Unsplash API error: {e}")

    seed = hash(topic) % 1000000
    for template in FALLBACK_URLS:
        url = template.replace("{seed}", str(seed))
        try:
            resp = requests.get(url, timeout=10, stream=True)
            if resp.ok:
                logger.info(f"Fallback image: {url.split('?')[0]}")
                return resp.url or url
        except Exception:
            continue

    logger.warning("All image sources failed")
    return None
