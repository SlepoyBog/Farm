import json
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


class SEOData:
    def __init__(self, title: str, description: str, keywords: str, article_html: str):
        self.title = title
        self.description = description
        self.keywords = keywords
        self.article_html = article_html

    def to_dict(self) -> dict:
        return {
            "seo_title": self.title,
            "seo_description": self.description,
            "seo_keywords": self.keywords,
        }


async def optimize_article(
    client: DeepSeekClient,
    topic: str,
    niche: str,
    outline: list[str],
    article: str,
) -> SEOData:
    logger.info(f"Optimizing article for SEO: {topic}")

    system_prompt, user_template = _load_seo_prompt()
    outline_str = json.dumps(outline, ensure_ascii=False)
    user_prompt = (
        user_template.replace("{{topic}}", topic)
        .replace("{{niche}}", niche)
        .replace("{{outline}}", outline_str)
        .replace("{{article}}", article)
    )

    try:
        result = await client.call_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=500,
        )

        seo_html = result.get("article_html", "")
        seo_data = SEOData(
            title=result.get("seo_title", topic),
            description=result.get("seo_description", ""),
            keywords=result.get("seo_keywords", ""),
            article_html=seo_html if seo_html.strip() else article,
        )

        logger.info(f"SEO title: {seo_data.title}")
        logger.info(f"SEO keywords: {seo_data.keywords}")
        return seo_data

    except Exception as e:
        logger.warning(f"SEO optimization failed: {e}. Using original article.")
        return SEOData(
            title=topic,
            description="",
            keywords="",
            article_html=article,
        )


def save_metadata(slug: str, topic: str, seo: SEOData):
    meta_path = Path("output") / f"{slug}.meta.json"
    data = {
        "topic": topic,
        "slug": slug,
        "seo_title": seo.title,
        "seo_description": seo.description,
        "seo_keywords": seo.keywords,
    }
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"SEO metadata saved to: {meta_path}")


def _load_seo_prompt() -> tuple[str, str]:
    prompt_path = Path("prompts") / "seo_optimizer.prompter"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")
    parts = content.split("---", 1)
    if len(parts) == 2:
        system_prompt = parts[0].strip()
        user_prompt = parts[1].strip()
    else:
        system_prompt = ""
        user_prompt = parts[0].strip()
    return system_prompt, user_prompt
