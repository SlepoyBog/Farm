import io
import logging
import os
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

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

WATERMARK_TEXT = "@farm_blog"


def _add_watermark(image_data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(img.width // 30, 16)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding = 10
        x = img.width - tw - padding
        y = img.height - th - padding
        draw.rectangle([x - 4, y - 4, x + tw + 4, y + th + 4], fill=(0, 0, 0, 100))
        draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 180))
        combined = Image.alpha_composite(img, overlay)
        buf = io.BytesIO()
        combined.convert("RGB").save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        logger.warning("Watermark error: %s", e)
        return image_data


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


def download_watermarked(image_url: str) -> tuple[bytes, str, str] | None:
    try:
        resp = requests.get(image_url, timeout=15)
        if not resp.ok:
            return None
        data = resp.content
        ct = resp.headers.get("content-type", "image/jpeg")
        ext = ".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"
        watermarked = _add_watermark(data)
        logger.info("Watermark added to image (%.1f KB -> %.1f KB)", len(data) / 1024, len(watermarked) / 1024)
        return watermarked, ct, ext
    except Exception as e:
        logger.warning("Watermark download error: %s", e)
        return None
