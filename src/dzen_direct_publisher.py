import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
DZEN_HOST = "https://dzen.ru"


def _init_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": DZEN_HOST,
    })

    raw_cookie = os.getenv("DZEN_SESSION_COOKIE", "")
    if not raw_cookie:
        return session

    for part in raw_cookie.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            session.cookies.set(key.strip(), val.strip(), domain=".dzen.ru")
            session.cookies.set(key.strip(), val.strip(), domain=".yandex.ru")
    return session


def _establish_session(session: requests.Session) -> bool:
    """Visit Dzen editor page to establish SSO session."""
    try:
        resp = session.get(
            f"{DZEN_HOST}/media/settings/publications/new",
            timeout=15,
        )
        logger.info(f"Dzen editor page: {resp.status_code} ({len(resp.content)} bytes)")

        if "is_autologin" in resp.text:
            import re as _re
            m = _re.search(r'host":"([^"]+)"', resp.text)
            if m:
                sso_url = m.group(1).replace("\\u002F", "/").replace("\\u0026", "&")
                logger.info(f"Following SSO: {sso_url[:80]}...")
                sso_resp = session.get(sso_url, timeout=15)
                logger.info(f"SSO response: {sso_resp.status_code}")

        resp2 = session.get(
            f"{DZEN_HOST}/media/settings/publications/new",
            timeout=15,
        )
        logger.info(f"After SSO: {resp2.status_code} ({len(resp2.content)} bytes)")

        if "publications" in resp2.text or "publication" in resp2.text:
            logger.info("SSO session established!")
            return True

        logger.warning("SSO session could not be established")
        return False

    except Exception as e:
        logger.error(f"Session establishment error: {e}")
        return False


def _try_api_endpoints(session: requests.Session, title: str, body_html: str, image_url: Optional[str]) -> tuple[bool, str]:
    endpoints = [
        "/api/v1/publication/create",
        "/api/v1/publication",
        "/api/v1/media/publication/create",
        "/api/v1/user/publication/create",
        "/media/api/publication",
    ]

    csrf = ""
    for c in session.cookies:
        if "csrf" in c.name.lower() or "xsrf" in c.name.lower() or "token" in c.name.lower():
            csrf = c.value
            break

    for ep in endpoints:
        url = f"{DZEN_HOST}{ep}"
        headers = {}
        if csrf:
            headers["X-CSRF-Token"] = csrf
            headers["X-XSRF-Token"] = csrf
        headers["X-Requested-With"] = "XMLHttpRequest"

        for fmt in ["json", "form"]:
            try:
                if fmt == "json":
                    resp = session.post(url, json={
                        "title": title,
                        "content": body_html,
                        "is_public": True,
                    }, headers=headers, timeout=30)
                else:
                    resp = session.post(url, data={
                        "title": title,
                        "content": body_html,
                        "is_public": "1",
                    }, headers=headers, timeout=30)
                logger.info(f"{ep} [{fmt}]: {resp.status_code} {resp.text[:200]}")
                if resp.ok and resp.text.strip():
                    try:
                        data = resp.json()
                        if data.get("error") == 0 or data.get("publication_id") or data.get("id"):
                            pub_id = data.get("publication_id") or data.get("id") or "ok"
                            return True, f"Dzen published: {pub_id}"
                    except (json.JSONDecodeError, Exception):
                        if resp.ok:
                            return True, "Dzen published (unknown format)"
            except Exception as e:
                logger.debug(f"{ep} [{fmt}]: {e}")

    return False, "All API endpoints failed"


def _build_body_html(html_content: str, image_url: Optional[str]) -> str:
    if image_url:
        img = f'<figure><img src="{image_url}" alt="" /></figure>'
        return img + "\n\n" + html_content
    return html_content


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
    session = _init_session()

    if not _establish_session(session):
        logger.warning("Could not establish Dzen session — trying API anyway")

    body_html = _build_body_html(html_content, image_url)
    return _try_api_endpoints(session, title, body_html, image_url)
