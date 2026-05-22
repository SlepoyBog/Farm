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

    # Strip HTML tags for plain text
    import html as html_module
    text = re.sub(r'<[^>]+>', '\n', content_no_h1)
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


def publish_to_vk(
    access_token: str,
    group_id: str,
    title: str,
    html_content: str,
    niche: str,
    from_group: int = 1,
    raw_text: str | None = None,
) -> tuple[bool, int | None]:
    """
    Publish adapted article to VK group wall.
    
    Args:
        access_token: VK API access token (with wall posting permissions)
        group_id: VK group ID (numeric, without minus sign, e.g. "186888784")
        title: Article title
        html_content: Article HTML content
        niche: Content niche for hashtag generation
        from_group: 1 to post on behalf of group, 0 for user
    
    Returns:
        tuple[bool, int | None] — (success, post_id or None)
    """
    if not access_token or not group_id:
        logger.warning("VK not configured. Skipping publication.")
        return False, None
    
    logger.info(f"Publishing article to VK: {title}")
    
    # Adapt content for VK style (use raw_text if pre-formatted)
    post_text = raw_text if raw_text else adapt_for_vk(title, html_content, niche)
    
    # Extract numeric ID from group_id (remove "club" prefix if present)
    numeric_id = group_id
    if numeric_id.startswith("club"):
        numeric_id = numeric_id[4:]
    if numeric_id.startswith("public"):
        numeric_id = numeric_id[6:]
    
    # VK API wall.post - use data instead of params for POST
    url = "https://api.vk.com/method/wall.post"
    data = {
        "access_token": access_token,
        "v": "5.199",
        "owner_id": f"-{numeric_id}",
        "from_group": from_group,
        "message": post_text,
    }
    
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
