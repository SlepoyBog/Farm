import hashlib
import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OK_API_FB = "https://api.ok.ru/fb.do"


def _session_secret(access_token: str, app_secret: str) -> str:
    return hashlib.md5(f"{access_token}{app_secret}".encode()).hexdigest()


def _sign(params: dict, secret: str) -> str:
    sorted_str = "".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.md5(f"{sorted_str}{secret}".encode()).hexdigest()


def _api_call(
    method: str,
    params: dict,
    access_token: str,
    public_key: str,
    app_secret: str,
) -> dict:
    secret = _session_secret(access_token, app_secret)
    all_params = {"application_key": public_key, "format": "json", "method": method}
    all_params.update(params)
    sig = _sign(all_params, secret)
    all_params["sig"] = sig
    all_params["access_token"] = access_token

    try:
        resp = requests.post(OK_API_FB, data=all_params, timeout=30)
        data = resp.json()
        if "error_code" in data:
            logger.error("OK API error %s: %s", data.get("error_code"), data.get("error_msg"))
            return {"error": data}
        return data
    except Exception as e:
        logger.error("OK API call failed: %s", e)
        return {"error": str(e)}


def adapt_for_ok(title: str, html_content: str) -> str:
    content = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html_content, flags=re.DOTALL)
    content = re.sub(r'`{3,}(?:html)?\s*|\s*`{3,}', '', content)
    content = re.sub(r'~{3,}(?:html)?\s*|\s*~{3,}', '', content)
    import html as hm
    text = hm.unescape(re.sub(r'<[^>]+>', '', content))
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    title_clean = re.sub(r'^-\s*', '', title).strip()
    body = text[:8000]
    return f"{title_clean}\n\n{body}"


def _upload_photo(
    access_token: str, public_key: str, app_secret: str,
    group_id: str, image_url: str,
) -> Optional[str]:
    result = _api_call("photos.getUploadUrl", {"gid": group_id}, access_token, public_key, app_secret)
    upload_url = result.get("upload_url")
    if not upload_url:
        return None
    try:
        img = requests.get(image_url, timeout=15)
        if not img.ok:
            return None
        up = requests.post(upload_url, files={"pic": ("photo.jpg", img.content, "image/jpeg")}, timeout=30)
        data = up.json()
        if "photos" in data:
            return data["photos"][0]["id"]
    except Exception as e:
        logger.warning("OK photo upload error: %s", e)
    return None


def publish_to_ok(
    access_token: str,
    public_key: str,
    app_secret: str,
    group_id: str,
    title: str,
    html_content: str,
    image_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    if not all([access_token, public_key, app_secret, group_id]):
        logger.warning("OK.ru not configured. Skipping.")
        return False, None

    logger.info("Publishing to OK.ru: %s", title)
    post_text = adapt_for_ok(title, html_content)

    params: dict = {"gid": group_id, "message": post_text, "type": "GROUP_THEME"}

    photo_id = None
    if image_url:
        photo_id = _upload_photo(access_token, public_key, app_secret, group_id, image_url)
        if photo_id:
            attach = json.dumps([{"type": "photo", "id": photo_id, "text": title}], ensure_ascii=False)
            params["attachment"] = attach

    result = _api_call("wall.post", params, access_token, public_key, app_secret)
    if "error" in result:
        logger.error("OK publish failed: %s", result["error"])
        return False, None

    post_id = result.get("id")
    logger.info("OK post published! ID: %s", post_id)
    return True, str(post_id) if post_id else None
