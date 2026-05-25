import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.deepseek_client import DeepSeekClient
from src.feedback_loop import inject_recommendations, record_publication
from src.trend_analyzer import detect_trending_niche
from src.site_generator import generate_site
from src.image_provider import get_image_url

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/process.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize DeepSeek client
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
if not DEEPSEEK_API_KEY:
    logger.error("DEEPSEEK_API_KEY not found in .env file!")
    sys.exit(1)

client = DeepSeekClient(api_key=DEEPSEEK_API_KEY)


def load_prompt(name: str) -> tuple[str, str]:
    """
    Load a prompt file from prompts/ directory.
    Returns (system_prompt, user_prompt_template).
    """
    prompt_path = Path("prompts") / f"{name}.prompter"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")

    # Split by --- separator
    parts = content.split("---", 1)
    if len(parts) == 2:
        system_prompt = parts[0].strip()
        user_prompt = parts[1].strip()
    else:
        system_prompt = ""
        user_prompt = parts[0].strip()

    return system_prompt, user_prompt


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


TOPICS_POOL_PATH = Path("data") / "topics_pool.json"


def _load_topic_pool() -> dict:
    if TOPICS_POOL_PATH.exists():
        try:
            return json.loads(TOPICS_POOL_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return {"generated_at": None, "topics": {}}
    return {"generated_at": None, "topics": {}}


def _save_topic_pool(pool: dict):
    TOPICS_POOL_PATH.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")


async def _refill_topic_pool(niche: str, pool: dict):
    """Generate 50 topics for niche via 1 API call and store in pool."""
    logger.info(f"Refilling topic pool for niche: {niche}")
    try:
        system_prompt, user_template = load_prompt("generate_topics")
        user_prompt = user_template.replace("{{niche}}", niche).replace("{{count}}", "50")

        response = await client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.8,
            max_tokens=2000,
        )

        topics = _parse_topic_list(response)
        if topics:
            pool["generated_at"] = datetime.now().isoformat()
            pool.setdefault("topics", {})[niche] = topics
            _save_topic_pool(pool)
            logger.info(f"Added {len(topics)} topics to pool for '{niche}'")
            return topics
    except Exception as e:
        logger.warning(f"Topic pool refill failed: {e}")
    return []


def _parse_topic_list(response: str) -> list[str]:
    lines = response.strip().split("\n")
    topics = []
    for line in lines:
        line = line.strip()
        line = re.sub(r"^[-*\d]+[.)]\s*", "", line).strip()
        if line and not line.startswith("```") and len(line) > 5:
            topics.append(line)
    if not topics:
        try:
            parsed = json.loads(response.strip())
            if isinstance(parsed, list):
                topics = [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    if not topics:
        topics = [l.strip() for l in lines if len(l.strip()) > 5]
    return topics[:50]


async def generate_topics(niche: str) -> list[str]:
    """Generate topics using local pool; refill weekly via 1 API call."""
    logger.info(f"Getting topics for niche: {niche}")

    pool = _load_topic_pool()
    niche_topics = pool.get("topics", {}).get(niche, [])
    generated_at = pool.get("generated_at")

    stale = not generated_at or (datetime.now() - datetime.fromisoformat(generated_at)) > timedelta(days=7)

    if not niche_topics or stale:
        logger.info(f"Topic pool for '{niche}' is empty or stale, refilling...")
        niche_topics = await _refill_topic_pool(niche, pool)

    if not niche_topics:
        logger.error(f"No topics available for niche: {niche}")
        return []

    batch = niche_topics[:15]
    remaining = niche_topics[15:]
    pool["topics"][niche] = remaining
    _save_topic_pool(pool)

    logger.info(f"Returning {len(batch)} topics from pool ({len(remaining)} remaining)")
    return batch


async def generate_outline(topic: str) -> list[str]:
    """Generate article outline using local templates (no API call)."""
    logger.info(f"Generating outline for topic: {topic}")

    templates_path = Path("data") / "outline_templates.json"
    if not templates_path.exists():
        logger.warning("Outline templates not found, using default")
        return ["Введение", "Основная часть", "Заключение"]

    with templates_path.open("r", encoding="utf-8") as f:
        templates = json.load(f)

    niche = _detect_niche_for_topic(topic)
    niche_templates = templates.get(niche) or templates.get("default", templates["default"])
    outline = random.choice(niche_templates)

    logger.info(f"Template outline ({niche}): {outline}")
    return outline


def _detect_niche_for_topic(topic: str) -> str:
    """Try to infer niche from topic text using keyword matching."""
    topic_lower = topic.lower()
    niche_keywords = {
        "искусственный интеллект": ["ии", "нейросет", "искусствен", "ai", "deep", "gpt", "chatgpt", "машин"],
        "авто": ["авто", "машин", "электромоби", "двигател", "шин", "кроссовер", "парковк", "тюнинг", "автосервис"],
        "технологии": ["технологи", "гаджет", "смартфон", "инноваци", "цифров", "программ"],
        "здоровье": ["здоров", "медицин", "болезн", "лечени", "врач", "питани", "спорт"],
        "финансы": ["финанс", "денег", "крипт", "инвестици", "биткоин", "бюджет", "налог"],
        "бизнес": ["бизнес", "стартап", "предпринима", "маркетинг", "продаж", "реклам"],
        "образование": ["образован", "курс", "школ", "университет", "обучение", "студент"],
        "спорт": ["спорт", "футбол", "хоккей", "тренировк", "соревнова"],
        "кино": ["кино", "фильм", "сериал", "актер", "режиссер"],
        "путешествия": ["путешеств", "турист", "отдых", "поездк", "билет", "отель"],
    }
    for niche, keywords in niche_keywords.items():
        for kw in keywords:
            if kw in topic_lower:
                return niche
    return "default"


async def generate_article(topic: str, outline: list[str]) -> str:
    """Write a full article based on topic and outline."""
    logger.info(f"Writing article for topic: {topic}")

    system_prompt, user_template = load_prompt("write_article")
    # Inject feedback-loop recommendations into the system prompt
    system_prompt = inject_recommendations(system_prompt)
    outline_str = json.dumps(outline, ensure_ascii=False)
    user_prompt = (
        user_template.replace("{{topic}}", topic)
        .replace("{{outline}}", outline_str)
    )

    article = await client.call(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=2000,
    )

    logger.info(f"Article written. Length: {len(article)} chars")
    return article


async def critique_article(article: str, outline: list[str]) -> tuple[float, str]:
    """Critique the article and return (score, feedback)."""
    logger.info("Critiquing article...")

    system_prompt, user_template = load_prompt("critique_article")
    outline_str = json.dumps(outline, ensure_ascii=False)
    user_prompt = (
        user_template.replace("{{article}}", article)
        .replace("{{outline}}", outline_str)
    )

    result = await client.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.2,
        max_tokens=2000,
    )

    score = float(result.get("score", 0))
    feedback = result.get("feedback", "No feedback provided")

    logger.info(f"Article critique score: {score}/10")
    return score, feedback


async def rewrite_article(article: str, feedback: str) -> str:
    """Rewrite article based on feedback."""
    logger.info("Rewriting article based on feedback...")

    system_prompt, user_template = load_prompt("rewrite_article")
    user_prompt = (
        user_template.replace("{{article}}", article)
        .replace("{{feedback}}", feedback)
    )

    rewritten = await client.call(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.6,
        max_tokens=2000,
    )

    logger.info(f"Article rewritten. Length: {len(rewritten)} chars")
    return rewritten


def html_to_telegram_text(html: str) -> str:
    """Convert HTML article to Telegram-compatible text with formatting.
    
    Telegram supports only: <b>, <i>, <u>, <s>, <code>, <pre>, <a href>
    """
    # Strip markdown code fences (model sometimes wraps HTML in ```html ... ```)
    html = re.sub(r'```(?:html)?\s*', '', html)
    html = re.sub(r'~~~(?:html)?\s*', '', html)
    # Strip excessive whitespace (spaces, tabs) while preserving newlines
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'^\s+', '', html, flags=re.MULTILINE)

    # First, decode HTML entities BEFORE tag processing
    import html as html_module
    html = html_module.unescape(html)
    
    # Convert headings to bold with newlines
    html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'<b>\1</b>\n\n', html, flags=re.DOTALL)
    html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'<b>\1</b>\n\n', html, flags=re.DOTALL)
    html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'<b>\1</b>\n\n', html, flags=re.DOTALL)
    # Convert <p> to plain text with newline
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html, flags=re.DOTALL)
    # Convert <ul> and <li>
    html = re.sub(r'<ul[^>]*>', '', html)
    html = re.sub(r'</ul>', '', html)
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', html, flags=re.DOTALL)
    # Convert <ol> and <li>
    html = re.sub(r'<ol[^>]*>', '', html)
    html = re.sub(r'</ol>', '', html)
    # Normalize <strong> and <b> to Telegram-compatible <b>
    html = re.sub(r'<strong[^>]*>', '<b>', html)
    html = re.sub(r'</strong>', '</b>', html)
    html = re.sub(r'<b[^>]*>', '<b>', html)
    html = re.sub(r'</b>', '</b>', html)
    # Normalize <i> and <em> to Telegram-compatible <i>
    html = re.sub(r'<em[^>]*>', '<i>', html)
    html = re.sub(r'</em>', '</i>', html)
    html = re.sub(r'<i[^>]*>', '<i>', html)
    html = re.sub(r'</i>', '</i>', html)
    # Keep <code>, <pre>, <a> as-is (they are Telegram-compatible)
    # Remove all other HTML tags
    html = re.sub(r'<(?!/?(?:b|i|code|pre|a)(?:\s[^>]*)?>)[^>]+>', '', html)
    # Clean up excessive newlines
    html = re.sub(r'\n{3,}', '\n\n', html)
    # Escape special Telegram characters in plain text (outside tags)
    # Telegram HTML mode only needs < > & escaped, but we handle
    # plain-text special chars for safety
    result_parts = []
    i = 0
    while i < len(html):
        if html[i] == '<':
            end = html.find('>', i)
            if end != -1:
                result_parts.append(html[i:end+1])
                i = end + 1
            else:
                result_parts.append('&lt;')
                i += 1
        elif html[i] == '&':
            result_parts.append('&amp;')
            i += 1
        else:
            result_parts.append(html[i])
            i += 1
    html = ''.join(result_parts)

    return html.strip()


def _truncate_html(text: str, max_chars: int) -> str:
    """Truncate HTML text at word boundary without breaking tags."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = max(truncated.rfind(" "), truncated.rfind("\n"))
    if last_space > 0:
        truncated = truncated[:last_space]
    last_open = truncated.rfind("<")
    last_close = truncated.rfind(">")
    if last_open > last_close:
        truncated = truncated[:last_open]
    open_tags = []
    i = 0
    while i < len(truncated):
        if truncated[i] == "<":
            end = truncated.find(">", i)
            if end != -1:
                tag = truncated[i + 1 : end].split()[0]
                if not tag.startswith("/"):
                    open_tags.append(tag)
                elif open_tags and open_tags[-1] == tag[1:]:
                    open_tags.pop()
                i = end + 1
            else:
                i += 1
        else:
            i += 1
    for tag in reversed(open_tags):
        truncated += f"</{tag}>"
    return truncated


def publish_to_telegram(title: str, html_content: str, image_url: str | None = None) -> tuple[bool, int | None]:
    """
    OLD APPROACH (sendMessage + link_preview, без фото в Дзен):
    Раскомментировать блок ниже и удалить новый код для отката.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Skipping publication.")
        return False, None

    logger.info(f"Publishing article to Telegram: {title}")

    content_no_h1 = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html_content, flags=re.DOTALL)
    clean_title = re.sub(r'^-\s*', '', title).strip()
    body_text = html_to_telegram_text(content_no_h1)
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    message = f"<b>{clean_title}</b>\n\n{body_text}"
    if len(message) > 4096:
        message = message[:4096]

    first_msg_id = None
    success = True
    photo_msg_id = None

    try:
        # Step 1: sendPhoto (image + caption) — Dzen picks this up
        if image_url:
            caption = clean_title
            if len(caption) > 900:
                caption = caption[:900]

            photo_resp = requests.post(f"{base_url}/sendPhoto", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
            }, timeout=30)

            if photo_resp.status_code == 200:
                photo_msg_id = photo_resp.json()["result"]["message_id"]
                first_msg_id = photo_msg_id
                logger.info(f"Telegram photo sent (id: {photo_msg_id})")
            else:
                logger.warning(f"sendPhoto failed ({photo_resp.status_code}), fallback to link_preview")

        # Step 2: sendMessage with full text (reply to photo if sent)
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        }
        if photo_msg_id:
            payload["reply_to_message_id"] = photo_msg_id
            payload["link_preview_options"] = {"is_disabled": True}
        elif image_url:
            payload["link_preview_options"] = {
                "is_disabled": False, "url": image_url, "prefer_large_media": True,
            }
        else:
            payload["link_preview_options"] = {"is_disabled": True}

        if "<" in message and ">" in message:
            payload["parse_mode"] = "HTML"

        resp = requests.post(f"{base_url}/sendMessage", json=payload, timeout=30)

        if resp.status_code == 400:
            import html as html_module
            plain = re.sub(r'<[^>]+>', '', message)
            plain = html_module.unescape(plain)
            payload.pop("parse_mode", None)
            payload["text"] = plain
            resp = requests.post(f"{base_url}/sendMessage", json=payload, timeout=30)

        resp.raise_for_status()
        msg_id = resp.json()["result"]["message_id"]
        if not first_msg_id:
            first_msg_id = msg_id
        logger.info(f"Telegram message sent (id: {msg_id})")

    except Exception as e:
        logger.error(f"Failed to send to Telegram: {e}", exc_info=True)
        success = False

    return success, first_msg_id


async def enhance_for_tg(html_article: str, niche: str) -> str:
    """Rewrite article HTML for Telegram with trends and engagement."""
    system_prompt, user_template = load_prompt("tg_trend_editor")
    user_prompt = (
        user_template.replace("{{article}}", html_article)
        .replace("{{niche}}", niche)
    )
    try:
        result = await client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=1500,
        )
        result = result.strip()
        if len(result) < 50:
            logger.warning(f"TG enhancement too short ({len(result)} chars), using original")
            return html_article
        return result
    except Exception as e:
        logger.warning(f"TG enhancement failed, using original HTML: {e}")
        return html_article





def _extract_title(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return "Без названия"


async def run_batch_seo(client: DeepSeekClient, niche: str):
    """Run SEO optimization once on all articles in output/."""
    logger.info("Running batch SEO optimization...")
    output_dir = Path("output")
    html_files = sorted(output_dir.glob("*.html"))
    if not html_files:
        logger.info("No articles to optimize.")
        return

    from src.seo_optimizer import optimize_article, save_metadata

    for fpath in html_files:
        slug = fpath.stem
        meta_path = output_dir / f"{slug}.meta.json"
        outline_path = output_dir / f"{slug}.outline.json"

        if not meta_path.exists() or not outline_path.exists():
            logger.warning(f"Skipping {slug}: missing metadata or outline")
            continue

        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        topic = meta.get("topic", slug)
        article = fpath.read_text(encoding="utf-8")

        with outline_path.open("r", encoding="utf-8") as f:
            outline = json.load(f)

        seo = await optimize_article(client, topic, niche, outline, article)
        save_metadata(slug, topic, seo)

        fpath.write_text(seo.article_html, encoding="utf-8")
        logger.info(f"SEO optimized: {slug}.html")

        outline_path.unlink(missing_ok=True)

    logger.info(f"Batch SEO complete for {len(html_files)} articles.")


async def process_topic(topic: str, niche: str, semaphore: asyncio.Semaphore):
    """Process a single topic through the full pipeline."""
    async with semaphore:
        start_time = time.time()
        logger.info(f"{'='*60}")
        logger.info(f"Processing topic: {topic}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Generate outline
            outline = await generate_outline(topic)
            if not outline:
                logger.error(f"Failed to generate outline for: {topic}")
                return

            # Step 2: Write article draft
            article = await generate_article(topic, outline)

            # Step 3: TG trend rewrite
            logger.info(f"Enhancing article for Telegram trends...")
            tg_article = await enhance_for_tg(article, niche)

            # Step 4: Save article + outline to files
            slug = slugify(topic)
            os.makedirs("output", exist_ok=True)
            output_path = Path("output") / f"{slug}.html"
            output_path.write_text(article, encoding="utf-8")
            logger.info(f"Article saved to: {output_path}")

            outline_path = Path("output") / f"{slug}.outline.json"
            outline_path.write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")

            # Get image for this niche/topic
            image_url = get_image_url(niche, topic)

            meta = {"topic": topic, "niche": niche}
            if image_url:
                meta["image_url"] = image_url
            meta_path = Path("output") / f"{slug}.meta.json"
            json.dump(meta, meta_path.open("w", encoding="utf-8"), ensure_ascii=False)

            # Step 5: Publish to Telegram (with enhanced content)
            tg_title = _extract_title(article)
            tg_ok, tg_msg_id = publish_to_telegram(tg_title, tg_article, image_url)

            # Step 6: Publish to VK (base article, VK publisher converts HTML)
            vk_ok = False
            vk_post_id_local = None
            try:
                from src.vk_publisher import publish_to_vk as publish_vk
                vk_ok, vk_post_id_local = publish_vk(
                    access_token=VK_ACCESS_TOKEN,
                    group_id=VK_GROUP_ID,
                    title=tg_title,
                    html_content=article,
                    niche=niche,
                    image_url=image_url,
                )
            except Exception as e:
                logger.warning(f"VK publish failed for '{topic}': {e}")

            # Step 7: Record publication for feedback loop
            vk_numeric = VK_GROUP_ID
            if vk_numeric:
                if vk_numeric.startswith("club"):
                    vk_numeric = vk_numeric[4:]
                if vk_numeric.startswith("public"):
                    vk_numeric = vk_numeric[6:]
            vk_owner_id = f"-{vk_numeric}" if vk_numeric else None

            clean_topic = re.sub(r"^-\s*\S?\s*", "", topic).strip()
            record_publication(
                topic=clean_topic,
                title=tg_title,
                niche=niche,
                tg_message_id=tg_msg_id,
                vk_post_id=vk_post_id_local,
                vk_owner_id=vk_owner_id,
            )

            elapsed = time.time() - start_time
            logger.info(f"Topic '{topic}' processed in {elapsed:.1f}s")
            return topic, article, article

        except Exception as e:
            logger.error(f"Error processing topic '{topic}': {e}", exc_info=True)
            return None


async def main():
    """Main orchestrator function."""
    parser = argparse.ArgumentParser(description="AI Content Farm")
    parser.add_argument("--full", action="store_true", help="Process all topics (default: test mode, 1 topic)")
    args = parser.parse_args()

    niche = await detect_trending_niche(client)

    logger.info(f"{'='*60}")
    logger.info(f"AI Content Farm - Starting")
    logger.info(f"Trending niche: {niche}")
    logger.info(f"{'='*60}")

    # Step 1: Generate topics
    topics = await generate_topics(niche)
    if not topics:
        logger.error("No topics generated. Exiting.")
        return

    if not args.full:
        topics = topics[:1]
        logger.info("TEST MODE: processing 1 topic (use --full for all)")

    # Save topics to queue file
    queue_path = Path("data") / "topics_queue.txt"
    queue_path.write_text("\n".join(topics), encoding="utf-8")
    logger.info(f"Topics saved to queue: {queue_path}")

    # Step 2: Process topics in parallel (max 5 concurrent)
    semaphore = asyncio.Semaphore(5)
    tasks = [process_topic(topic, niche, semaphore) for topic in topics]
    results = await asyncio.gather(*tasks)

    successful = len([r for r in results if r is not None])
    logger.info(f"Processed {successful}/{len(topics)} topics successfully.")

    logger.info(f"{'='*60}")
    logger.info("All topics processed successfully!")
    logger.info(f"{'='*60}")

    await run_batch_seo(client, niche)
    generate_site()


if __name__ == "__main__":
    asyncio.run(main())
