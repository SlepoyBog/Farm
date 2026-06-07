import logging

logger = logging.getLogger(__name__)

def publish_to_dzen(
    access_token: str,
    group_id: str,
    title: str,
    html_content: str,
    niche: str,
    image_url: str | None = None,
    topic: str = "",
) -> tuple[bool, str]:
    """
    Publish article to VK group for Dzen cross-posting.

    Dzen and VK are part of the same ecosystem. When a VK group is connected
    to Dzen (Settings → Channels → VK in Dzen), posts to the VK wall are
    automatically cross-posted to Dzen with FULL text (no 1024 limit).

    Args:
        access_token: VK API access token (group or user)
        group_id: VK group ID (e.g., "club123456")
        title: Article title
        html_content: Full article HTML
        niche: Content niche
        image_url: Optional image URL
        topic: Original topic

    Returns:
        (success, message) tuple
    """
    if not access_token or not group_id:
        logger.warning("VK not configured — Dzen publishing unavailable.")
        return False, "VK not configured"

    logger.info(f"Publishing to Dzen (via VK): {title}")

    try:
        from src.vk_publisher import publish_to_vk

        vk_ok, vk_post_id = publish_to_vk(
            access_token=access_token,
            group_id=group_id,
            title=title,
            html_content=html_content,
            niche=niche,
            image_url=image_url,
        )

        if vk_ok:
            msg = f"Dzen (via VK) — post ID: {vk_post_id}"
            logger.info(msg)

            if not image_url:
                logger.info(
                    "Note: VK photo upload requires a user token. "
                    "Dzen will receive the article text but no photo."
                )

            logger.info(
                "IMPORTANT: For automatic Dzen cross-posting, connect your VK group "
                "to Dzen at: dzen.ru → profile → channels → connect VK"
            )
            return True, msg
        else:
            return False, "VK publish failed"

    except Exception as e:
        logger.error(f"Dzen publish failed: {e}")
        return False, str(e)
