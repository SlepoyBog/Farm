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
SITE_URL = (os.getenv("SITE_URL") or "").rstrip("/")

NICHE_NAMES = {
    "искусственный интеллект": "AI",
    "авто": "Авто",
    "технологии": "Технологии",
    "здоровье": "Здоровье",
    "финансы": "Финансы",
    "бизнес": "Бизнес",
    "образование": "Образование",
    "спорт": "Спорт",
    "кино": "Кино",
    "путешествия": "Путешествия",
}

HEAD = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <meta name="description" content="{{description}}">
    <meta name="robots" content="index, follow">
    <link rel="alternate" type="application/rss+xml" title="{{site_name}}" href="/rss.xml">
    <link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
    <style>
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f4f6f8;color:#1a1a2e;line-height:1.6}
        .container{max-width:860px;margin:0 auto;padding:0 20px}
        header{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:#fff;padding:0}
        .header-inner{max-width:860px;margin:0 auto;padding:30px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:15px}
        header h1{font-size:1.5em}
        header h1 a{color:#fff;text-decoration:none}
        header p{opacity:.75;font-size:.9em;margin-top:4px}
        .nav-links{display:flex;gap:8px;flex-wrap:wrap}
        .nav-links a{color:#fff;text-decoration:none;font-size:.82em;opacity:.7;padding:4px 10px;border-radius:20px;background:rgba(255,255,255,.08);transition:all .15s}
        .nav-links a:hover{opacity:1;background:rgba(255,255,255,.15)}
        .search-box{width:100%;max-width:860px;margin:0 auto;padding:16px 20px 0}
        .search-box input{width:100%;padding:12px 16px;border:1px solid #dde1e6;border-radius:10px;font-size:.95em;background:#fff;outline:none;transition:border .15s}
        .search-box input:focus{border-color:#4361ee}
        .article-list{margin-top:10px}
        .article-card{background:#fff;border-radius:12px;padding:20px;margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,.05);transition:transform .15s,box-shadow .15s;display:flex;gap:16px}
        .article-card:hover{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,.08)}
        .article-card .card-img{width:120px;min-height:90px;border-radius:8px;background:#e9ecef;flex-shrink:0;overflow:hidden}
        .article-card .card-img img{width:100%;height:100%;object-fit:cover}
        .article-card .card-body{flex:1;min-width:0}
        .article-card h2{font-size:1.05em;margin-bottom:6px}
        .article-card h2 a{color:#1a1a2e;text-decoration:none}
        .article-card h2 a:hover{color:#4361ee}
        .article-card .meta{font-size:.82em;color:#6c757d;margin-bottom:4px}
        .article-card .meta .niche-tag{display:inline-block;background:#eef2ff;color:#4361ee;padding:1px 8px;border-radius:10px;font-size:.85em;margin-right:6px}
        .article-card p{color:#495057;font-size:.9em;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
        .page-header{text-align:center;padding:30px 20px 10px}
        .page-header h2{font-size:1.3em;color:#1a1a2e}
        .page-header p{color:#6c757d;font-size:.9em;margin-top:4px}
        .pagination{text-align:center;padding:20px}
        .pagination a{display:inline-block;padding:8px 20px;background:#4361ee;color:#fff;border-radius:8px;text-decoration:none;font-size:.9em}
        .pagination a:hover{opacity:.85}
        footer{text-align:center;padding:30px 20px;color:#6c757d;font-size:.82em}
        footer a{color:#4361ee;text-decoration:none}
        article{background:#fff;border-radius:12px;padding:40px;margin-top:20px;box-shadow:0 1px 4px rgba(0,0,0,.05)}
        article h1{font-size:1.6em;margin-bottom:16px;color:#1a1a2e}
        article h2{font-size:1.25em;margin:28px 0 12px;color:#1a1a2e}
        article p{margin-bottom:16px;color:#212529}
        article ul,article ol{margin:0 0 16px 20px;color:#212529}
        article li{margin-bottom:6px}
        .meta{font-size:.85em;color:#6c757d;margin-bottom:20px}
        .related{margin-top:30px;padding-top:20px;border-top:1px solid #e9ecef}
        .related h3{font-size:1.1em;margin-bottom:12px;color:#1a1a2e}
        .related a{display:block;padding:8px 0;color:#4361ee;text-decoration:none;font-size:.95em}
        .related a:hover{text-decoration:underline}
        @media(max-width:640px){
            .header-inner{flex-direction:column;text-align:center;padding:20px}
            .nav-links{justify-content:center}
            .article-card{flex-direction:column}
            .article-card .card-img{width:100%;height:160px}
            article{padding:20px}
        }
        .no-results{text-align:center;padding:40px;color:#6c757d}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <div>
                <h1><a href="/">{{site_name}}</a></h1>
                <p>{{site_description}}</p>
            </div>
            <div class="nav-links">
                {{nav_links}}
            </div>
        </div>
    </header>
    <div class="search-box">
        <input type="text" id="search" placeholder="Поиск статей..." oninput="filterArticles(this.value)">
    </div>
    {{content}}
    <footer>
        <p>&copy; {{year}} {{site_name}} &mdash; <a href="/rss.xml">RSS</a> | <a href="/sitemap.xml">Sitemap</a> | <a href="/all.html">Все статьи</a></p>
    </footer>
    <script>
    function filterArticles(q){q=q.toLowerCase();document.querySelectorAll('.article-card').forEach(c=>{const t=c.textContent.toLowerCase();c.style.display=t.includes(q)?'':'none'});const n=document.querySelector('.no-results');if(n){const v=[...document.querySelectorAll('.article-card')].some(c=>c.style.display!='none');n.style.display=v?'none':'block'}}
    </script>
</body>
</html>"""

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <meta name="description" content="{{description}}">
    <meta name="keywords" content="{{keywords}}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{{title}}">
    <meta property="og:description" content="{{description}}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{{url}}">
    <meta property="og:image" content="{{og_image}}">
    <meta property="og:site_name" content="{{site_name}}">
    <link rel="canonical" href="{{url}}">
    <link rel="alternate" type="application/rss+xml" title="{{site_name}}" href="/rss.xml">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
    <style>
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f4f6f8;color:#1a1a2e;line-height:1.8}
        .container{max-width:740px;margin:0 auto;padding:0 20px}
        .topnav{background:#1a1a2e;padding:10px 0}
        .topnav .container{display:flex;align-items:center;justify-content:space-between}
        .topnav a{color:rgba(255,255,255,.8);text-decoration:none;font-size:.88em}
        .topnav a:hover{color:#fff}
        article{background:#fff;border-radius:12px;padding:40px;margin:20px 0;box-shadow:0 1px 4px rgba(0,0,0,.05)}
        article h1{font-size:1.6em;margin-bottom:16px;color:#1a1a2e}
        article h2{font-size:1.25em;margin:28px 0 12px;color:#1a1a2e}
        article h3{font-size:1.1em;margin:20px 0 10px;color:#1a1a2e}
        article p{margin-bottom:16px;color:#212529;line-height:1.8}
        article ul,article ol{margin:0 0 16px 24px;color:#212529}
        article li{margin-bottom:6px}
        article blockquote{border-left:3px solid #4361ee;padding:10px 16px;margin:0 0 16px;background:#f8f9ff;color:#495057;border-radius:0 8px 8px 0}
        article img{max-width:100%;height:auto;border-radius:8px;margin:10px 0}
        article a{color:#4361ee}
        .meta{font-size:.85em;color:#6c757d;margin-bottom:20px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        .meta .niche-tag{display:inline-block;background:#eef2ff;color:#4361ee;padding:2px 10px;border-radius:12px;font-size:.88em;text-decoration:none}
        .related{margin-top:30px;padding-top:20px;border-top:1px solid #e9ecef}
        .related h3{font-size:1.1em;margin-bottom:12px;color:#1a1a2e}
        .related a{display:block;padding:8px 0;color:#4361ee;text-decoration:none;font-size:.95em}
        .related a:hover{text-decoration:underline}
        footer{text-align:center;padding:30px 20px;color:#6c757d;font-size:.82em}
        footer a{color:#4361ee;text-decoration:none}
        @media(max-width:640px){article{padding:20px}}
    </style>
</head>
<body>
    <div class="topnav">
        <div class="container">
            <a href="/">&larr; На главную</a>
            <a href="/all.html">Все статьи</a>
        </div>
    </div>
    <main class="container">
        <article>
            <h1>{{title}}</h1>
            <div class="meta">
                <span>{{date}}</span>
                {{niche_tag}}
            </div>
            {{og_image_html}}
            {{content}}
            {{related_html}}
        </article>
    </main>
    <footer>
        <p>&copy; {{year}} {{site_name}} &mdash; <a href="/rss.xml">RSS</a> | <a href="/sitemap.xml">Sitemap</a></p>
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
    content = kwargs.pop("content", None)
    for k, v in kwargs.items():
        result = result.replace("{{%s}}" % k, v)
    if content is not None:
        result = result.replace("{{content}}", content)
    return result


def _find_related(articles: list[dict], current_idx: int, count: int = 3) -> list[dict]:
    current = articles[current_idx]
    current_keywords = set(current.get("keywords", "").lower().split(", "))
    current_title = current.get("title", "").lower()
    scored = []
    for i, art in enumerate(articles):
        if i == current_idx:
            continue
        score = 0
        art_keywords = set(art.get("keywords", "").lower().split(", "))
        overlap = current_keywords & art_keywords
        score += len(overlap) * 3
        art_title = art.get("title", "").lower()
        common = set(current_title.split()) & set(art_title.split())
        score += len(common)
        if score > 0:
            scored.append((score, art))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:count]]


def _build_card(img_html: str, slug: str, title: str, date: str, niche: str, snippet: str) -> str:
    niche_tag = '<span class="niche-tag">%s</span>' % NICHE_NAMES.get(niche, niche) if niche else ""
    return (
        '<div class="article-card" data-niche="%s">'
        '%s'
        '<div class="card-body">'
        '<h2><a href="%s.html">%s</a></h2>'
        '<div class="meta">%s %s</div>'
        "<p>%s...</p></div></div>"
    ) % (niche, img_html, slug, title, niche_tag, date, snippet)


def _niche_page_html(niche_key: str, articles: list[dict]) -> str:
    niche_name = NICHE_NAMES.get(niche_key, niche_key)
    cards = []
    for art in articles:
        img = '<div class="card-img"><img src="%s" alt=""/></div>' % art["og_image"] if art.get("og_image") else ""
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        cards.append(_build_card(img, art["slug"], art["title"], art["date"], art.get("niche", ""), snippet))
    return '<div class="page-header"><h2>📂 %s</h2><p>%d статей</p></div><div class="article-list">%s</div>' % (
        niche_name, len(cards), "\n".join(cards)
    )


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
        niche = meta.get("niche", "")

        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc)
        months_ru = {1: "января", 2: "февраля", 3: "марта", 4: "апреля",
                     5: "мая", 6: "июня", 7: "июля", 8: "августа",
                     9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"}
        date_str = f"{mtime.day} {months_ru[mtime.month]} {mtime.year}"

        og_image = meta.get("image_url", "")
        og_image_html = (
            '<div style="margin-bottom:20px"><img src="%s" alt="%s" style="width:100%%;max-width:720px;border-radius:8px"></div>'
        ) % (og_image, clean_title or title) if og_image else ""

        niche_tag = ""
        if niche and niche in NICHE_NAMES:
            niche_tag = '<a href="/niche-%s.html" class="niche-tag">%s</a>' % (niche, NICHE_NAMES[niche])

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
            "og_image": og_image,
            "og_image_html": og_image_html,
            "niche": niche,
            "niche_tag": niche_tag,
        })

    nav_links = "".join(
        '<a href="/niche-%s.html">%s</a>' % (key, name)
        for key, name in NICHE_NAMES.items()
    )

    # --- Generate individual article pages ---
    for i, art in enumerate(articles):
        related = _find_related(articles, i, count=3)
        related_html = ""
        if related:
            links = "\n".join('<a href="%s.html">%s</a>' % (r["slug"], r["title"]) for r in related)
            related_html = '<div class="related"><h3>📖 Читайте также</h3>%s</div>' % links

        url = "%s/%s.html" % (SITE_URL, art["slug"]) if SITE_URL else "/%s.html" % art["slug"]
        page = _render(
            ARTICLE_TEMPLATE,
            title=art["title"],
            description=art["description"],
            keywords=art["keywords"],
            url=url,
            og_image=art["og_image"],
            site_name=SITE_NAME,
            date=art["date"],
            og_image_html=art["og_image_html"],
            niche_tag=art["niche_tag"],
            content=art["content"],
            related_html=related_html,
            year=art["year"],
        )
        (SITE_DIR / ("%s.html" % art["slug"])).write_text(page, encoding="utf-8")

    logger.info("  Generated %d article pages" % len(articles))

    # --- Generate "all articles" page ---
    all_cards = []
    for art in articles:
        img = '<div class="card-img"><img src="%s" alt=""/></div>' % art["og_image"] if art.get("og_image") else '<div class="card-img"></div>'
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        all_cards.append(_build_card(img, art["slug"], art["title"], art["date"], art["niche"], snippet))

    all_page = _render(
        HEAD,
        title="Все статьи — " + SITE_NAME,
        description=SITE_DESCRIPTION,
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        nav_links=nav_links,
        content='<div class="page-header"><h2>📚 Все статьи</h2><p>%d статей</p></div><div class="article-list">%s</div>' % (len(all_cards), "\n".join(all_cards)),
        year=str(datetime.now().year),
    )
    (SITE_DIR / "all.html").write_text(all_page, encoding="utf-8")
    logger.info("  Generated: all.html (%d articles)" % len(all_cards))

    # --- Generate niche pages ---
    niche_articles: dict[str, list[dict]] = {}
    for art in articles:
        n = art.get("niche", "")
        if not n or n not in NICHE_NAMES:
            n = "технологии"
        niche_articles.setdefault(n, []).append(art)

    for niche_key, niche_arts in niche_articles.items():
        niche_content = _niche_page_html(niche_key, niche_arts)
        page = _render(
            HEAD,
            title=NICHE_NAMES.get(niche_key, niche_key) + " — " + SITE_NAME,
            description="Статьи по теме «%s»" % NICHE_NAMES.get(niche_key, niche_key),
            site_name=SITE_NAME,
            site_description=SITE_DESCRIPTION,
            nav_links=nav_links,
            content=niche_content,
            year=str(datetime.now().year),
        )
        (SITE_DIR / ("niche-%s.html" % niche_key)).write_text(page, encoding="utf-8")

    logger.info("  Generated %d niche category pages" % len(niche_articles))

    # --- Generate index page (latest 20 articles) ---
    index_cards = []
    for art in articles[:20]:
        img = '<div class="card-img"><img src="%s" alt=""/></div>' % art["og_image"] if art.get("og_image") else ""
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        index_cards.append(_build_card(img, art["slug"], art["title"], art["date"], art["niche"], snippet))

    index_all_link = '<div class="pagination"><a href="/all.html">Все статьи →</a></div>' if len(articles) > 20 else ""

    index_page = _render(
        HEAD,
        title=SITE_NAME,
        description=SITE_DESCRIPTION,
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        nav_links=nav_links,
        content='<div class="article-list">%s</div>%s' % ("\n".join(index_cards), index_all_link),
        year=str(datetime.now().year),
    )
    (SITE_DIR / "index.html").write_text(index_page, encoding="utf-8")
    logger.info("  Generated: index.html (latest 20 of %d articles)" % len(articles))

    _generate_sitemap(articles)
    _generate_rss(articles)
    _generate_robots()

    logger.info("Site generated in %s/ — %d articles, %d niches" % (SITE_DIR, len(articles), len(niche_articles)))


def _generate_sitemap(articles: list[dict]):
    base = SITE_URL or ""
    pages = ['<url><loc>%s/</loc><priority>1.0</priority></url>' % base]
    pages.append('<url><loc>%s/all.html</loc><priority>0.9</priority></url>' % base)
    seen = set()
    for art in articles:
        n = art.get("niche", "")
        if n and n not in seen:
            pages.append('<url><loc>%s/niche-%s.html</loc><priority>0.7</priority></url>' % (base, n))
            seen.add(n)
    for art in articles:
        pages.append(
            '<url><loc>%s/%s.html</loc><lastmod>%s</lastmod><priority>0.8</priority></url>'
            % (base, art['slug'], art['iso_date'])
        )
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(pages) + "\n</urlset>"
    (SITE_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")
    logger.info("  Generated: sitemap.xml (%d URLs)" % len(pages))


def _generate_rss(articles: list[dict]):
    base = SITE_URL or ""
    items = []
    for art in articles:
        description = xml_escape(re.sub(r"<[^>]+>", "", art["content"])[:500])
        full_content = _rss_full_content(art)
        enclosure = ""
        if art.get("og_image"):
            enclosure = '<enclosure url="%s" type="image/jpeg" length="0"/>\n' % xml_escape(art["og_image"])
        item = (
            "<item>\n"
            "<title>%s</title>\n"
            "<link>%s/%s.html</link>\n"
            "<guid>%s/%s.html</guid>\n"
            "<pubDate>%s</pubDate>\n"
            "<description>%s</description>\n"
            "%s"
            "<content:encoded><![CDATA[%s]]></content:encoded>\n"
            "</item>"
        ) % (
            xml_escape(art['title']),
            base, art['slug'],
            base, art['slug'],
            art['mtime'].strftime('%a, %d %b %Y 00:00:00 +0000'),
            description,
            enclosure,
            full_content,
        )
        items.append(item)
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:media="http://search.yahoo.com/mrss/">\n'
        "<channel>\n"
        "<title>%s</title>\n"
        "<link>%s</link>\n"
        "<description>%s</description>\n"
        "<language>ru</language>\n"
        '<atom:link href="%s/rss.xml" rel="self" type="application/rss+xml"/>\n'
        "%s\n"
        "</channel>\n</rss>"
    ) % (xml_escape(SITE_NAME), base, xml_escape(SITE_DESCRIPTION), base, "\n".join(items))
    (SITE_DIR / "rss.xml").write_text(rss, encoding="utf-8")
    logger.info("  Generated: rss.xml (%d items)" % len(items))


def _rss_full_content(art: dict) -> str:
    title_esc = xml_escape(art["title"])
    parts = ["<h1>%s</h1>" % title_esc]
    if art.get("og_image"):
        parts.append('<img src="%s" alt="%s" style="max-width:100%%"/>' % (xml_escape(art["og_image"]), title_esc))
    content = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", art["content"], flags=re.DOTALL)
    parts.append(content)
    return "\n".join(parts)


def _generate_robots():
    base = SITE_URL or ""
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: %s/sitemap.xml\n"
    ) % base
    (SITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    logger.info("  Generated: robots.txt")


def generate_cname(domain: str):
    (SITE_DIR / "CNAME").write_text(domain.strip() + "\n", encoding="utf-8")
    logger.info("  Generated: CNAME (%s)" % domain)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    if len(sys.argv) > 2 and sys.argv[1] == "--cname":
        generate_cname(sys.argv[2])
    generate_site()
