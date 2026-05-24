import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://news.yandex.ru/security.rss",
    "https://news.yandex.ru/auto.rss",
    "https://news.yandex.ru/technology.rss",
    "https://news.yandex.ru/business.rss",
    "https://news.yandex.ru/finances.rss",
    "https://news.yandex.ru/health.rss",
    "https://news.yandex.ru/sport.rss",
    "https://news.yandex.ru/science.rss",
    "https://news.yandex.ru/gadgets.rss",
]

RSS_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
]


def _parse_rss_date(raw: str) -> Optional[datetime]:
    for fmt in RSS_DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def fetch_recent_headlines(hours: int = 6, max_total: int = 60) -> list[str]:
    headlines: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.iter("item"):
                pub_str = item.findtext("pubDate", "")
                if pub_str:
                    pub_dt = _parse_rss_date(pub_str)
                    if pub_dt and pub_dt < cutoff:
                        continue
                title = item.findtext("title", "")
                if title and len(title) > 10:
                    headlines.append(title.strip())
        except Exception as e:
            logger.warning(f"RSS fetch failed for {url}: {e}")

    headlines = headlines[:max_total]
    logger.info(f"Fetched {len(headlines)} recent headlines from RSS")
    return headlines
