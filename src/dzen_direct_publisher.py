import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DZEN_API_BASE = "https://dzen.ru/api/v1"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def _build_headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://dzen.ru",
        "Referer": "https://dzen.ru/media/settings/publications/new",
        "X-Requested-With": "XMLHttpRequest",
    }


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


def _extract_publication_id(data: dict) -> str:
    for key in ("publication_id", "id", "data", "result"):
        val = data.get(key)
        if isinstance(val, dict):
            nested = val.get("publication_id") or val.get("id")
            if nested:
                return str(nested)
        elif val and isinstance(val, (str, int)):
            return str(val)
    return ""


def _cookie_is_valid(session: requests.Session) -> bool:
    try:
        resp = session.get("https://dzen.ru/api/v1/user/me", timeout=15)
        if resp.ok:
            data = resp.json()
            if data and data.get("status") != "error":
                return True
        logger.warning("Dzen cookie validation failed: %s — %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("Dzen cookie validation error: %s", e)
        return False


def publish_to_dzen_direct(
    title: str,
    html_content: str,
    image_url: Optional[str] = None,
    niche: str = "",
    topic: str = "",
) -> tuple[bool, str]:
    cookie = os.getenv("DZEN_SESSION_COOKIE")
    if not cookie:
        logger.warning("DZEN_SESSION_COOKIE not set — skipping direct Dzen publish.")
        return False, "DZEN_SESSION_COOKIE not configured"

    logger.info("Publishing directly to Dzen: %s", title)

    session = _get_session()

    if not _cookie_is_valid(session):
        return False, "DZEN_SESSION_COOKIE expired or invalid"

    text_only = re.sub(r"<[^>]+>", "", html_content)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    excerpt = text_only[:500]

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
        f"{DZEN_API_BASE}/media/publication/create",
    ]

    for endpoint in endpoints:
        try:
            resp = session.post(endpoint, json=payload, timeout=30)
            logger.info("Dzen API %s: %s — %s", endpoint, resp.status_code, resp.text[:300])

            if not resp.ok:
                logger.warning("Dzen API %s returned %s", endpoint, resp.status_code)
                continue

            try:
                data = resp.json()
            except json.JSONDecodeError:
                logger.warning("Dzen API %s returned non-JSON: %s", endpoint, resp.text[:200])
                continue

            pub_id = _extract_publication_id(data)
            if pub_id:
                logger.info("Dzen publish success! ID: %s", pub_id)
                return True, "Published to Dzen: %s" % pub_id

            logger.warning("Dzen API %s: unexpected response format: %s", endpoint, json.dumps(data, ensure_ascii=False)[:200])

        except requests.RequestException as e:
            logger.warning("Dzen API error at %s: %s", endpoint, e)
            continue

    logger.warning("Direct API failed for all endpoints — trying form-based publish...")
    return _publish_via_form(session, title, html_content, image_url)


def _clean_html_for_dzen(html: str, image_url: Optional[str] = None) -> str:
    if image_url:
        img_tag = '<img src="%s" alt="" style="max-width:100%%" />' % image_url
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

        payload = {
            "title": title,
            "content": _clean_html_for_dzen(html_content, image_url),
            "is_public": True,
        }

        resp = session.post(
            "https://dzen.ru/api/v1/user/publication/create",
            json=payload,
            timeout=30,
        )
        logger.info("Dzen fallback API: %s — %s", resp.status_code, resp.text[:300])
        if resp.ok:
            return True, "Published via Dzen fallback API"

        return False, "Dzen API failed: %s" % resp.text[:200]

    except Exception as e:
        logger.error("Dzen form publish error: %s", e)
        return False, str(e)
