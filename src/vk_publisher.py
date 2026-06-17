"""
VK (Vkontakte) publisher for AI Content Farm.
Adapts articles for VK style and publishes to VK group/wall.
"""

import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def adapt_for_vk(title: str, html_content: str, niche: str) -> str:
    """
    Adapt article content for VK style:
    - More emotional, engaging tone
    - Break into readable paragraphs/cards
    - Add hashtags
    - End with a question to drive engagement
    """
    # Strip h1 from content (title is added separately below, avoid duplication)
    content_no_h1 = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html_content, flags=re.DOTALL)

    # Strip markdown fences (AI sometimes wraps HTML in ```html ... ```)
    content_no_h1 = re.sub(r'`{3,}(?:html)?\s*|\s*`{3,}', '', content_no_h1)
    content_no_h1 = re.sub(r'~{3,}(?:html)?\s*|\s*~{3,}', '', content_no_h1)

    # Strip HTML tags for plain text
    import html as html_module
    # Block-level tags → newline (preserve paragraph structure)
    block_tags = r'</?(?:p|h[1-6]|li|div|ul|ol|br|hr|blockquote|table|tr|td|th|section|article|header|footer|nav|aside|figure|figcaption|details|summary|dl|dt|dd|address|fieldset|legend|main|menu)[^>]*>'
    text = re.sub(block_tags, '\n', content_no_h1)
    # Inline tags → empty (keep text flow unbroken)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_module.unescape(text)
    
    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    # Clean title
    clean_title = re.sub(r'^-\s*', '', title).strip()
    
    # Build VK post
    lines = text.split('\n')
    
    # Take up to 15000 chars (VK wall limit)
    body_lines = []
    char_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if char_count + len(line) > 15000:
            break
        body_lines.append(line)
        char_count += len(line)
    
    body = '\n\n'.join(body_lines)
    
    # Generate hashtags from niche and topic keywords
    hashtags = _generate_hashtags(niche, clean_title)
    
    # Engagement question
    question = _generate_question(clean_title)
    
    # Assemble the post
    post_parts = [
        f"🔥 {clean_title}",
        "",
        body,
        "",
        f"💬 {question}",
        "",
        hashtags,
    ]
    
    return '\n'.join(post_parts)


def _generate_hashtags(niche: str, title: str) -> str:
    """Generate relevant hashtags from niche and title."""
    # Base niche hashtag
    niche_words = niche.lower().split()
    niche_tag = '#' + ''.join(word.capitalize() for word in niche_words)
    
    # Extract keywords from title
    title_lower = title.lower()
    # Remove common words
    stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'как', 'что', 'это', 'не', 'от', 'до', 'о', 'об', 'без', 'за', 'из', 'у', 'к', 'а'}
    keywords = [w for w in re.findall(r'\w+', title_lower) if w not in stop_words and len(w) > 3]
    
    # Take up to 3 meaningful keywords as hashtags
    title_tags = []
    for kw in keywords[:3]:
        tag = '#' + ''.join(word.capitalize() for word in kw.split())
        if tag not in title_tags:
            title_tags.append(tag)
    
    # Combine all hashtags
    all_tags = [niche_tag] + title_tags
    
    # Add some general trending tags based on niche
    if 'искусственный интеллект' in niche.lower() or 'ии' in niche.lower():
        all_tags.extend(['#AI', '#Нейросети', '#Технологии'])
    elif 'технологи' in niche.lower():
        all_tags.extend(['#Технологии', '#Будущее', '#Инновации'])
    else:
        all_tags.append('#Технологии')
    
    return ' '.join(all_tags[:6])  # Max 6 hashtags


def _generate_question(title: str) -> str:
    """Generate an engaging question related to the topic."""
    questions = [
        f"А вы уже пробовали использовать ИИ для этой задачи? Делитесь опытом в комментариях! 👇",
        f"Как думаете, через 5 лет эта технология станет обыденностью? 🤔",
        f"Сталкивались с чем-то подобным? Расскажите свою историю! 💬",
        f"А что вы думаете по этому поводу? Жду ваши мысли в комментариях! 😊",
        f"Полезно было? Ставьте ❤️, если хотите больше таких материалов!",
        f"Согласны с автором? Или у вас другое мнение? Давайте обсудим! 👇",
    ]
    # Simple deterministic selection based on title length
    idx = len(title) % len(questions)
    return questions[idx]


def combine_for_vk(articles: list[tuple[str, str]], niche: str) -> str:
    """
    Combine multiple AI-enhanced articles into a single VK digest post.
    
    Args:
        articles: list of (title, vk_enhanced_text) tuples
        niche: content niche for hashtag generation
    
    Returns:
        Pre-formatted VK post text with all articles
    """
    parts = [f"🔥 Дайджест: {niche.capitalize()}", ""]
    
    for i, (title, vk_text) in enumerate(articles, 1):
        clean_title = re.sub(r'^[-\s]*', '', title).strip()
        
        parts.append(f"📌 {i}. {clean_title}")
        parts.append(vk_text)
        parts.append("───" if i < len(articles) else "")
    
    parts.append("💬 Как вам такая подборка? Делитесь мнением в комментариях! 👇")
    parts.append("")
    
    niche_words = niche.lower().split()
    niche_tag = '#' + ''.join(word.capitalize() for word in niche_words)
    hashtags = [niche_tag, '#AI', '#Нейросети', '#Технологии']
    parts.append(' '.join(hashtags))
    
    return '\n'.join(parts)


def _upload_wall_photo(access_token: str, group_id: str, image_url: str) -> str | None:
    upload_data = {}
    try:
        numeric_id = group_id
        if numeric_id.startswith("club"):
            numeric_id = numeric_id[4:]
        if numeric_id.startswith("public"):
            numeric_id = numeric_id[6:]

        logger.info(f"VK photo: getting upload server for group_id={numeric_id}")
        resp = requests.get(
            "https://api.vk.com/method/photos.getWallUploadServer",
            params={"access_token": access_token, "v": "5.199", "group_id": numeric_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data or "response" not in data:
            logger.error(f"VK upload server error: {data.get('error', 'no response')}")
            return None
        upload_url = data["response"]["upload_url"]
        logger.info("VK photo: upload server obtained")

        logger.info(f"VK photo: downloading from Unsplash: {image_url[:60]}...")
        img_resp = requests.get(image_url, timeout=15)
        img_resp.raise_for_status()
        content_type = img_resp.headers.get("content-type", "image/jpeg")
        ext = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
        logger.info(f"VK photo: downloaded {len(img_resp.content)} bytes, type={content_type}")

        up_resp = requests.post(
            upload_url,
            files={"photo": (f"image{ext}", img_resp.content, content_type)},
            timeout=30,
        )
        up_resp.raise_for_status()
        upload_data = up_resp.json()
        logger.info("VK photo: uploaded to VK server")

        save_resp = requests.post(
            "https://api.vk.com/method/photos.saveWallPhoto",
            data={
                "access_token": access_token,
                "v": "5.199",
                "group_id": numeric_id,
                "photo": upload_data["photo"],
                "server": upload_data["server"],
                "hash": upload_data["hash"],
            },
            timeout=15,
        )
        save_resp.raise_for_status()
        save_data = save_resp.json()
        if "error" in save_data:
            logger.error(f"VK save photo error: {save_data['error']}")
            return None

        photo = save_data["response"][0]
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        logger.info(f"VK photo uploaded: {attachment}")
        return attachment
    except requests.exceptions.HTTPError as e:
        logger.error(f"VK photo HTTP error: {e}", exc_info=True)
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"VK photo connection error: {e}", exc_info=True)
        return None
    except requests.exceptions.Timeout as e:
        logger.error(f"VK photo timeout error: {e}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"VK photo request error: {e}", exc_info=True)
        return None
    except KeyError as e:
        logger.error(f"VK photo unexpected response format (missing key {e}): {upload_data}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Failed to upload image to VK: {e}", exc_info=True)
        return None


def publish_to_vk(
    access_token: str,
    group_id: str,
    title: str,
    html_content: str,
    niche: str,
    from_group: int = 1,
    raw_text: str | None = None,
    image_url: str | None = None,
) -> tuple[bool, int | None]:
    if not access_token or not group_id:
        logger.warning("VK not configured. Skipping publication.")
        return False, None

    logger.info(f"Publishing article to VK: {title}")

    post_text = raw_text if raw_text else adapt_for_vk(title, html_content, niche)

    numeric_id = group_id
    if numeric_id.startswith("club"):
        numeric_id = numeric_id[4:]
    if numeric_id.startswith("public"):
        numeric_id = numeric_id[6:]

    attachments = []
    if image_url:
        photo_attachment = _upload_wall_photo(access_token, group_id, image_url)
        if photo_attachment:
            attachments.append(photo_attachment)

    url = "https://api.vk.com/method/wall.post"
    data = {
        "access_token": access_token,
        "v": "5.199",
        "owner_id": f"-{numeric_id}",
        "from_group": from_group,
        "message": post_text,
    }
    if attachments:
        data["attachments"] = ",".join(attachments)

    try:
        response = requests.post(url, data=data, timeout=30)
        logger.info(f"VK API response status: {response.status_code}")
        logger.info(f"VK API response text: {response.text[:500]}")

        if not response.text.strip():
            logger.error("VK API returned empty response. Check access token and group ID.")
            return False, None

        data = response.json()

        if "error" in data:
            error_msg = data["error"].get("error_msg", "Unknown error")
            error_code = data["error"].get("error_code", 0)
            logger.error(f"VK API error {error_code}: {error_msg}")
            return False, None

        post_id = data.get("response", {}).get("post_id", None)
        logger.info(f"VK post published successfully! Post ID: {post_id}")
        return True, post_id

    except Exception as e:
        logger.error(f"Failed to publish to VK: {e}", exc_info=True)
        return False, None
