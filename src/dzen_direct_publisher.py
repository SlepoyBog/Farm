import json
import logging
import os
import re
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DZEN_API_BASE = "https://dzen.ru/api/v1"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def _build_headers() -> dict:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://dzen.ru",
        "Referer": "https://dzen.ru/media/settings/publications/new",
        "X-Requested-With": "XMLHttpRequest",
    }
    session_cookie = os.getenv("DZEN_SESSION_COOKIE", "")
    if session_cookie:
        headers["Cookie"] = session_cookie
    return headers


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_build_headers())
    session_cookie = os.getenv("DZEN_SESSION_COOKIE", "")
    if session_cookie:
        for part in session_cookie.split(";"):
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                session.cookies.set(key.strip(), val.strip(), domain=".dzen.ru")
    return session


def publish_to_dzen_direct(
    title: str,
    html_content: str,
    image_url: Optional[str] = None,
    niche: str = "",
    topic: str = "",
) -> tuple[bool, str]:
    if not os.getenv("DZEN_SESSION_COOKIE"):
        logger.warning("DZEN_SESSION_COOKIE not set — skipping direct Dzen publish.")
        return False, "DZEN_SESSION_COOKIE not configured"

    logger.info(f"Publishing directly to Dzen: {title}")

    session = _get_session()

    # Strip HTML for plain-text excerpt
    text_only = re.sub(r"<[^>]+>", "", html_content)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    excerpt = text_only[:500]

    # Build article content in Dzen-compatible format
    body_html = _clean_html_for_dzen(html_content, image_url)

    payload = {
        "title": title,
        "subtitle": "",
        "content": body_html,
        "tags": [niche] if niche else [],
        "is_article": True,
        "is_public": True,
        "is_rss": True,
        "image_url": image_url or "",
        "excerpt": excerpt,
    }

    endpoints = [
        f"{DZEN_API_BASE}/publication/create",
        f"{DZEN_API_BASE}/publication",
        f"{DZEN_API_BASE}/media/publication/create",
        f"{DZEN_API_BASE}/content/create",
        "https://dzen.ru/api/v1/user/publication/create",
        "https://dzen.ru/api/v1/media/publication/create",
        "https://dzen.ru/api/v1/publish",
    ]

    for endpoint in endpoints:
        try:
            resp = session.post(
                endpoint,
                json=payload,
                timeout=30,
            )
            data = resp.json()
            logger.info(f"Dzen API {endpoint}: {resp.status_code} — {resp.text[:300]}")

            if resp.ok and data.get("error") == 0:
                pub_id = data.get("publication_id", data.get("id", ""))
                logger.info(f"Dzen publish success! ID: {pub_id}")
                return True, f"Published to Dzen: {pub_id}"

            if data.get("error") != 1:
                continue

        except Exception as e:
            logger.debug(f"Dzen API error at {endpoint}: {e}")
            continue

    logger.warning("Direct API failed, trying form-based publish...")
    return _publish_via_form(session, title, html_content, image_url)


def _clean_html_for_dzen(html: str, image_url: Optional[str] = None) -> str:
    if image_url:
        img_tag = f'<img src="{image_url}" alt="" style="max-width:100%" />'
        html = img_tag + "\n\n" + html
    return html


def _publish_via_form(
    session: requests.Session,
    title: str,
    html_content: str,
    image_url: Optional[str] = None,
) -> tuple[bool, str]:
    try:
        text_only = re.sub(r"<[^>]+>", "", html_content)
        text_only = re.sub(r"\s+", " ", text_only).strip()

        data = {
            "title": title,
            "text": text_only,
            "format": "text",
            "is_public": "1",
        }

        resp = session.post(
            "https://dzen.ru/media/api/publication",
            data=data,
            timeout=30,
        )
        logger.info(f"Dzen form publish: {resp.status_code} — {resp.text[:300]}")

        if resp.ok:
            return True, "Published via Dzen form"

        resp = session.post(
            "https://dzen.ru/api/v1/user/publication/create",
            json={
                "title": title,
                "content": _clean_html_for_dzen(html_content, image_url),
                "is_public": True,
            },
            timeout=30,
        )
        logger.info(f"Dzen fallback API: {resp.status_code} — {resp.text[:300]}")
        if resp.ok:
            return True, "Published via Dzen fallback API"

        return False, f"Dzen API failed: {resp.text[:200]}"

    except Exception as e:
        logger.error(f"Dzen form publish error: {e}")
        return False, str(e)
