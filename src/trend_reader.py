import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/top-headlines"

NEWSAPI_CATEGORIES = [
    "business",
    "technology",
    "health",
    "science",
    "sports",
    "entertainment",
]

REDDIT_FEEDS = [
    ("https://www.reddit.com/r/all/top.json?limit=25&t=day", "all"),
    ("https://www.reddit.com/r/worldnews/top.json?limit=10&t=day", "worldnews"),
    ("https://www.reddit.com/r/technology/top.json?limit=10&t=day", "technology"),
    ("https://www.reddit.com/r/science/top.json?limit=5&t=day", "science"),
]

FALLBACK_RSS = [
    "http://feeds.bbci.co.uk/news/rss.xml",
    "http://rss.cnn.com/rss/edition.rss",
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


def _fetch_newsapi() -> list[str]:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []

    headlines: list[str] = []
    for category in NEWSAPI_CATEGORIES:
        try:
            resp = requests.get(
                NEWSAPI_BASE,
                params={
                    "country": "ru",
                    "category": category,
                    "pageSize": 5,
                    "apiKey": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("articles", []):
                title = (article.get("title") or "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception as e:
            logger.warning(f"NewsAPI ({category}) failed: {e}")

    if headlines:
        logger.info(f"Fetched {len(headlines)} headlines from NewsAPI")
    return headlines


def _fetch_reddit() -> list[str]:
    headers = {"User-Agent": "FarmBot/1.0 (trend-reader)"}
    headlines: list[str] = []
    for url, name in REDDIT_FEEDS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                title = (child.get("data", {}).get("title") or "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception as e:
            logger.warning(f"Reddit ({name}) failed: {e}")

    if headlines:
        logger.info(f"Fetched {len(headlines)} headlines from Reddit")
    return headlines


def _fetch_rss() -> list[str]:
    headlines: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    for url in FALLBACK_RSS:
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

    if headlines:
        logger.info(f"Fetched {len(headlines)} headlines from RSS ({url})")
    return headlines


def fetch_recent_headlines(hours: int = 24, max_total: int = 50) -> list[str]:
    headlines = _fetch_newsapi()
    if not headlines:
        headlines = _fetch_reddit()
    if not headlines:
        headlines = _fetch_rss()

    if not headlines:
        logger.warning("No headlines fetched from any source")
        return []

    result = headlines[:max_total]
    logger.info(f"Total {len(result)} headlines for trend analysis")
    return result
