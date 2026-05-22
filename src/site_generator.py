import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SITE_DIR = Path("site")
OUTPUT_DIR = Path("output")

load_dotenv()

SITE_NAME = "AI Блог — технологии, тренды, инсайты"
SITE_DESCRIPTION = "Ежедневные статьи об искусственном интеллекте, технологиях и трендах."
SITE_URL = os.getenv("SITE_URL", "https://your-niche-blog.pages.dev")

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="robots" content="index, follow">
    <link rel="alternate" type="application/rss+xml" title="{site_name}" href="/rss.xml">
    <link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; line-height: 1.6; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 40px 20px; text-align: center; }}
        header h1 {{ font-size: 1.8em; margin-bottom: 10px; }}
        header p {{ opacity: 0.8; font-size: 1em; }}
        .article-list {{ margin-top: 20px; }}
        .article-card {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: transform 0.15s, box-shadow 0.15s; }}
        .article-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }}
        .article-card h2 {{ font-size: 1.2em; margin-bottom: 8px; }}
        .article-card h2 a {{ color: #1a1a2e; text-decoration: none; }}
        .article-card h2 a:hover {{ color: #4361ee; }}
        .article-card .meta {{ font-size: 0.85em; color: #6c757d; margin-bottom: 8px; }}
        .article-card p {{ color: #495057; font-size: 0.95em; }}
        footer {{ text-align: center; padding: 30px 20px; color: #6c757d; font-size: 0.85em; }}
        footer a {{ color: #4361ee; text-decoration: none; }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>{site_name}</h1>
            <p>{site_description}</p>
        </div>
    </header>
    <main class="container">
        <div class="article-list">{articles}</div>
    </main>
    <footer>
        <p>&copy; {year} {site_name} &mdash; <a href="/rss.xml">RSS</a> | <a href="/sitemap.xml">Sitemap</a></p>
    </footer>
</body>
</html>"""

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{keywords}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{url}">
    <meta property="og:site_name" content="{site_name}">
    <link rel="canonical" href="{url}">
    <link rel="alternate" type="application/rss+xml" title="{site_name}" href="/rss.xml">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; line-height: 1.8; }}
        .container {{ max-width: 720px; margin: 0 auto; padding: 20px; }}
        nav {{ background: #1a1a2e; padding: 12px 20px; }}
        nav a {{ color: #fff; text-decoration: none; font-size: 0.9em; opacity: 0.9; }}
        nav a:hover {{ opacity: 1; }}
        article {{ background: #fff; border-radius: 12px; padding: 30px; margin-top: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        article h1 {{ font-size: 1.6em; margin-bottom: 16px; color: #1a1a2e; }}
        article h2 {{ font-size: 1.3em; margin: 24px 0 12px; color: #1a1a2e; }}
        article p {{ margin-bottom: 14px; color: #212529; }}
        article ul, article ol {{ margin: 0 0 14px 20px; color: #212529; }}
        article li {{ margin-bottom: 6px; }}
        article strong {{ color: #1a1a2e; }}
        .meta {{ font-size: 0.85em; color: #6c757d; margin-bottom: 20px; }}
        footer {{ text-align: center; padding: 30px 20px; color: #6c757d; font-size: 0.85em; }}
        footer a {{ color: #4361ee; text-decoration: none; }}
        @media (max-width: 600px) {{ article {{ padding: 20px; }} }}
    </style>
</head>
<body>
    <nav>
        <div class="container"><a href="/">&larr; На главную</a></div>
    </nav>
    <main class="container">
        <article>
            <h1>{title}</h1>
            <div class="meta">{date}</div>
            {content}
        </article>
    </main>
    <footer>
        <p>&copy; {year} {site_name} &mdash; <a href="/rss.xml">RSS</a></p>
    </footer>
</body>
</html>"""


def _extract_first_sentence(html: str, max_len: int = 200) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    desc = sentences[0] if sentences else text
    if len(desc) > max_len:
        desc = desc[: max_len - 3] + "..."
    return desc


def _extract_keywords(html: str, title: str, max_kw: int = 6) -> str:
    text = re.sub(r"<[^>]+>", "", html).lower()
    words = re.findall(r"\w{4,}", text)
    stop = {"который", "чтобы", "также", "может", "этого", "всего", "после", "тогда", "даже", "очень"}
    freq = {}
    for w in words:
        if w not in stop and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq, key=freq.get, reverse=True)[:max_kw]
    title_kw = re.findall(r"\w{4,}", title.lower())
    combined = list(dict.fromkeys(title_kw + top))
    return ", ".join(combined[:max_kw])


def _parse_title(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return "Без названия"


def _strip_emojis(text: str) -> str:
    emoji = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF\u2600-\u27BF"
        "\uFE00-\uFE0F]+",
        flags=re.UNICODE,
    )
    return emoji.sub("", text).strip()


def _read_metadata(slug: str) -> dict:
    meta_path = OUTPUT_DIR / f"{slug}.meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _render(template: str, **kwargs) -> str:
    result = template
    for k, v in kwargs.items():
        result = result.replace(f"{{{k}}}", v)
    return result


def generate_site():
    logger.info("=" * 60)
    logger.info("Generating SEO static site...")
    logger.info("=" * 60)

    SITE_DIR.mkdir(parents=True, exist_ok=True)

    html_files = sorted(
        [f for f in OUTPUT_DIR.glob("*.html") if f.name != "_sample.txt"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not html_files:
        logger.warning("No HTML files found in output/")
        return

    articles = []
    for fpath in html_files:
        content = fpath.read_text(encoding="utf-8")
        slug = fpath.stem
        title = _parse_title(content)
        description = _extract_first_sentence(content)
        clean_title = _strip_emojis(title)

        meta = _read_metadata(slug)
        if meta.get("seo_description"):
            description = meta["seo_description"]
        keywords = meta.get("seo_keywords", "") or _extract_keywords(content, title)

        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc)
        months_ru = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
        }
        date_str = f"{mtime.day} {months_ru[mtime.month]} {mtime.year}"

        articles.append({
            "slug": slug,
            "title": clean_title or title,
            "description": description,
            "keywords": keywords,
            "content": content,
            "date": date_str,
            "iso_date": mtime.strftime("%Y-%m-%d"),
            "year": str(mtime.year),
            "mtime": mtime,
        })

    for art in articles:
        url = f"{SITE_URL}/{art['slug']}.html"
        page = _render(
            ARTICLE_TEMPLATE,
            title=art["title"],
            description=art["description"],
            keywords=art["keywords"],
            url=url,
            site_name=SITE_NAME,
            date=art["date"],
            content=art["content"],
            year=art["year"],
        )
        (SITE_DIR / f"{art['slug']}.html").write_text(page, encoding="utf-8")
        logger.info(f"  Generated: {art['slug']}.html")

    cards = []
    for art in articles:
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:200]
        cards.append(
            f'<div class="article-card">'
            f'<h2><a href="{art["slug"]}.html">{art["title"]}</a></h2>'
            f'<div class="meta">{art["date"]}</div>'
            f"<p>{snippet}...</p></div>"
        )

    index_html = _render(
        INDEX_TEMPLATE,
        title=SITE_NAME,
        description=SITE_DESCRIPTION,
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        year=str(datetime.now().year),
        articles="\n".join(cards),
    )
    (SITE_DIR / "index.html").write_text(index_html, encoding="utf-8")
    logger.info(f"  Generated: index.html ({len(cards)} articles)")

    _generate_sitemap(articles)
    _generate_rss(articles)
    _generate_robots()

    logger.info(f"Site generated in {SITE_DIR}/ — {len(articles)} articles")


def _generate_sitemap(articles: list[dict]):
    pages = [f"<url><loc>{SITE_URL}/</loc><priority>1.0</priority></url>"]
    for art in articles:
        pages.append(
            f"<url><loc>{SITE_URL}/{art['slug']}.html</loc>"
            f"<lastmod>{art['iso_date']}</lastmod>"
            f"<priority>0.8</priority></url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(pages)
        + "\n</urlset>"
    )
    (SITE_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")
    logger.info("  Generated: sitemap.xml")


def _generate_rss(articles: list[dict]):
    items = []
    for art in articles:
        snippet = xml_escape(re.sub(r"<[^>]+>", "", art["content"])[:300])
        items.append(
            f"<item>\n"
            f"<title>{xml_escape(art['title'])}</title>\n"
            f"<link>{SITE_URL}/{art['slug']}.html</link>\n"
            f"<guid>{SITE_URL}/{art['slug']}.html</guid>\n"
            f"<pubDate>{art['mtime'].strftime('%a, %d %b %Y 00:00:00 +0000')}</pubDate>\n"
            f"<description>{snippet}</description>\n"
            f"</item>"
        )
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        f"<title>{xml_escape(SITE_NAME)}</title>\n"
        f"<link>{SITE_URL}</link>\n"
        f"<description>{xml_escape(SITE_DESCRIPTION)}</description>\n"
        f"<language>ru</language>\n"
        f'<atom:link href="{SITE_URL}/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n</channel>\n</rss>"
    )
    (SITE_DIR / "rss.xml").write_text(rss, encoding="utf-8")
    logger.info("  Generated: rss.xml")


def _generate_robots():
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    (SITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    logger.info("  Generated: robots.txt")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    generate_site()
