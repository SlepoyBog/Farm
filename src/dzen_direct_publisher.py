import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

VK_API_URL = "https://api.vk.com/method"
API_VERSION = "5.199"


def publish_to_dzen_direct(
    title: str,
    html_content: str,
    image_url: Optional[str] = None,
    niche: str = "",
    topic: str = "",
) -> tuple[bool, str]:
    vk_token = os.getenv("VK_ACCESS_TOKEN")
    if not vk_token:
        logger.warning("VK_ACCESS_TOKEN not set — Dzen publishing unavailable.")
        return False, "VK_ACCESS_TOKEN not configured"

    logger.info(f"Publishing to Dzen via VK content API: {title}")

    text = re.sub(r"<[^>]+>", "", html_content)
    text = re.sub(r"\s+", " ", text).strip()

    attachments = []
    if image_url:
        try:
            img_resp = requests.get(image_url, timeout=15)
            if img_resp.ok:
                upload = requests.get(
                    f"{VK_API_URL}/content.getUploadServer",
                    params={
                        "access_token": vk_token,
                        "v": API_VERSION,
                        "type": "image",
                    },
                    timeout=15,
                ).json()
                upload_url = upload.get("response", {}).get("upload_url")
                if upload_url:
                    up = requests.post(upload_url, files={
                        "file": ("image.jpg", img_resp.content, "image/jpeg"),
                    }, timeout=30).json()
                    attachments.append(json.dumps(up))
        except Exception as e:
            logger.warning(f"Image upload failed: {e}")

    try:
        payload = {
            "access_token": vk_token,
            "v": API_VERSION,
            "title": title,
            "text": text,
            "is_published": 1,
            "is_dzen": 1,
        }
        if attachments:
            payload["attachments"] = ",".join(attachments)

        resp = requests.post(
            f"{VK_API_URL}/content.create",
            data=payload,
            timeout=30,
        )
        data = resp.json()
        logger.info(f"VK content.create: {resp.status_code} — {resp.text[:300]}")

        if "error" not in data:
            content_id = data.get("response", {}).get("id", "ok")
            logger.info(f"Dzen published via VK content API! ID: {content_id}")
            return True, f"Published to Dzen: {content_id}"

        logger.warning(f"VK content.create error: {data.get('error', {}).get('error_msg', 'unknown')}")

    except Exception as e:
        logger.warning(f"VK content.create failed: {e}")

    try:
        group_id = os.getenv("VK_GROUP_ID", "")
        numeric_id = re.sub(r"[^\d]", "", group_id)

        resp = requests.post(
            f"{VK_API_URL}/wall.post",
            data={
                "access_token": vk_token,
                "v": API_VERSION,
                "owner_id": f"-{numeric_id}",
                "from_group": 1,
                "message": f"📰 {title}\n\n{text}",
                "dzen": 1,
            },
            timeout=30,
        )
        data = resp.json()
        logger.info(f"VK wall.post (dzen=1): {resp.status_code} — {resp.text[:300]}")

        if "error" not in data:
            post_id = data.get("response", {}).get("post_id", "ok")
            logger.info(f"Published to VK+Dzen! Post ID: {post_id}")
            return True, f"Published to VK+Dzen: {post_id}"

        logger.warning(f"VK wall.post error: {data.get('error', {}).get('error_msg', 'unknown')}")
        return False, f"VK API error: {data.get('error', {}).get('error_msg', 'unknown')}"

    except Exception as e:
        logger.error(f"Dzen publish failed: {e}")
        return False, str(e)
