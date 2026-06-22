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

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#fafafa;--surface:#fff;--text:#1a1a2e;--text-secondary:#6b7280;--accent:#2563eb;--accent-hover:#1d4ed8;--border:#e5e7eb;--radius:12px;--shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04)}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased}
.container{max-width:840px;margin:0 auto;padding:0 24px}
header{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
.header-inner{max-width:840px;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;height:60px}
header h1{font-size:1.1em;font-weight:700;letter-spacing:-.3px}
header h1 a{color:var(--text);text-decoration:none}
.nav-links{display:flex;gap:4px;align-items:center}
.nav-links a{color:var(--text-secondary);text-decoration:none;font-size:.85em;padding:6px 12px;border-radius:8px;transition:all .15s}
.nav-links a:hover{color:var(--text);background:#f3f4f6}
.nav-toggle{display:none;background:none;border:none;font-size:1.4em;cursor:pointer;padding:4px 8px;border-radius:8px;color:var(--text)}
.search-wrap{padding:20px 0 0;max-width:840px;margin:0 auto}
.search-wrap input{width:100%;padding:12px 16px;border:1px solid var(--border);border-radius:10px;font-size:.93em;background:var(--surface);outline:none;transition:border .2s}
.search-wrap input:focus{border-color:var(--accent)}
.article-list{display:flex;flex-direction:column;gap:12px;padding:16px 0}
.article-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;transition:all .15s;display:flex;gap:16px}
.article-card:hover{border-color:#d1d5db;box-shadow:var(--shadow)}
.article-card .card-img{width:140px;min-height:100px;border-radius:8px;overflow:hidden;flex-shrink:0;background:#f3f4f6}
.article-card .card-img img{width:100%;height:100%;object-fit:cover;transition:transform .3s}
.article-card:hover .card-img img{transform:scale(1.03)}
.article-card .card-body{flex:1;min-width:0}
.article-card h2{font-size:1.05em;margin-bottom:4px;line-height:1.4}
.article-card h2 a{color:var(--text);text-decoration:none}
.article-card h2 a:hover{color:var(--accent)}
.article-card .meta{font-size:.8em;color:var(--text-secondary);display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.article-card .niche-tag{display:inline-block;background:#eef2ff;color:var(--accent);padding:1px 8px;border-radius:6px;font-size:.85em;font-weight:500;text-decoration:none}
.article-card p{color:#4b5563;font-size:.88em;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.page-header{text-align:center;padding:32px 0 8px}
.page-header h2{font-size:1.3em;font-weight:700}
.page-header p{color:var(--text-secondary);font-size:.9em;margin-top:4px}
.pagination{text-align:center;padding:20px 0}
.pagination a{display:inline-block;padding:10px 24px;background:var(--accent);color:#fff;border-radius:8px;text-decoration:none;font-size:.9em;font-weight:500}
.pagination a:hover{background:var(--accent-hover)}
footer{text-align:center;padding:40px 24px;color:var(--text-secondary);font-size:.82em;border-top:1px solid var(--border);margin-top:40px}
footer a{color:var(--accent);text-decoration:none}
.reading-progress{position:fixed;top:0;left:0;height:2px;background:var(--accent);z-index:200;width:0%;transition:width .1s}
article{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:48px;margin:24px 0}
article h1{font-size:2em;font-weight:800;margin-bottom:12px;line-height:1.3;letter-spacing:-.5px}
article .article-meta{font-size:.88em;color:var(--text-secondary);margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-wrap:wrap;align-items:center}
article .article-meta .niche-tag{background:#eef2ff;color:var(--accent);padding:2px 10px;border-radius:6px;font-size:.9em;font-weight:500;text-decoration:none}
article h2{font-size:1.35em;font-weight:700;margin:32px 0 12px;line-height:1.35}
article h3{font-size:1.12em;font-weight:600;margin:24px 0 10px}
article p{margin-bottom:16px;color:#374151;line-height:1.8;font-size:.98em}
article ul,article ol{margin:0 0 16px 24px;color:#374151}
article li{margin-bottom:6px;line-height:1.7}
article blockquote{border-left:3px solid var(--accent);padding:12px 20px;margin:0 0 16px;background:#f8faff;color:#374151;border-radius:0 8px 8px 0;font-style:italic}
article img{max-width:100%;height:auto;border-radius:8px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.06)}
article a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
article a:hover{color:var(--accent-hover)}
article code{background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:.9em;font-family:'JetBrains Mono','Fira Code',monospace}
article pre{background:#1a1a2e;color:#e5e7eb;padding:16px 20px;border-radius:8px;overflow-x:auto;margin:0 0 16px;font-size:.9em;line-height:1.5}
.breadcrumbs{font-size:.85em;color:var(--text-secondary);margin-bottom:16px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.breadcrumbs a{color:var(--text-secondary);text-decoration:none}
.breadcrumbs a:hover{color:var(--accent)}
.related{margin-top:32px;padding-top:24px;border-top:1px solid var(--border)}
.related h3{font-size:1.1em;font-weight:600;margin-bottom:12px}
.related a{display:block;padding:10px 0;color:var(--accent);text-decoration:none;font-size:.95em;border-bottom:1px solid var(--border)}
.related a:last-child{border:none}
.related a:hover{color:var(--accent-hover)}
.no-results{text-align:center;padding:60px 20px;color:var(--text-secondary)}
@media(max-width:680px){
.header-inner{padding:0 16px}
.nav-links{display:none;position:absolute;top:60px;left:0;right:0;background:var(--surface);border-bottom:1px solid var(--border);flex-direction:column;padding:8px 16px}
.nav-links.open{display:flex}
.nav-toggle{display:block}
.article-card{flex-direction:column}
.article-card .card-img{width:100%;height:180px}
article{padding:24px 16px}
article h1{font-size:1.5em}
.container{padding:0 16px}
}"""

HEAD = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <meta name="description" content="{{description}}">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{{og_title}}">
    <meta property="og:description" content="{{og_description}}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{{og_url}}">
    <meta property="og:image" content="{{og_image}}">
    <meta property="og:site_name" content="{{site_name}}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{og_title}}">
    <meta name="twitter:description" content="{{og_description}}">
    <meta name="twitter:image" content="{{og_image}}">
    <link rel="alternate" type="application/rss+xml" title="{{site_name}}" href="/rss.xml">
    <link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%232563eb'/><text x='50' y='68' font-size='55' text-anchor='middle' fill='white'>A</text></svg>">
    <style>{{css}}</style>
</head>
<body>
    {{jsonld}}
    <header>
        <div class="header-inner">
            <h1><a href="/">{{site_name}}</a></h1>
            <button class="nav-toggle" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">☰</button>
            <div class="nav-links">{{nav_links}}</div>
        </div>
    </header>
    <div class="search-wrap">
        <input type="text" id="search" placeholder="Поиск статей..." oninput="filterArticles(this.value)">
    </div>
    {{content}}
    <footer>
        <p>&copy; {{year}} {{site_name}} &mdash; <a href="/rss.xml">RSS</a> · <a href="/sitemap.xml">Sitemap</a> · <a href="/all.html">Все статьи</a></p>
    </footer>
    <script>
    function filterArticles(q){q=q.toLowerCase();const cards=document.querySelectorAll('.article-card');let visible=0;cards.forEach(c=>{const t=c.textContent.toLowerCase();const match=t.includes(q);c.style.display=match?'':'none';if(match)visible++});const nr=document.querySelector('.no-results');if(nr)nr.style.display=visible?'none':'block'}
    function updateProgress(){const s=document.documentElement.scrollTop;const h=document.documentElement.scrollHeight-document.documentElement.clientHeight;const p=h>0?(s/h)*100:0;const bar=document.querySelector('.reading-progress');if(bar)bar.style.width=p+'%'}
    window.addEventListener('scroll',updateProgress)
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
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{title}}">
    <meta name="twitter:description" content="{{description}}">
    <meta name="twitter:image" content="{{og_image}}">
    <link rel="canonical" href="{{url}}">
    <link rel="alternate" type="application/rss+xml" title="{{site_name}}" href="/rss.xml">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%232563eb'/><text x='50' y='68' font-size='55' text-anchor='middle' fill='white'>A</text></svg>">
    <style>{{css}}</style>
    {{jsonld}}
</head>
<body>
    <div class="reading-progress"></div>
    <header>
        <div class="header-inner">
            <h1><a href="/">{{site_name}}</a></h1>
            <button class="nav-toggle" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">☰</button>
            <div class="nav-links">{{nav_links}}</div>
        </div>
    </header>
    <main class="container">
        <article>
            <div class="breadcrumbs">
                <a href="/">Главная</a>
                <span>/</span>
                <a href="{{niche_url}}">{{niche_name}}</a>
                <span>/</span>
                <span>{{title}}</span>
            </div>
            <h1>{{title}}</h1>
            <div class="article-meta">
                <span>{{date}}</span>
                <span>·</span>
                <span>{{reading_time}}</span>
                {{niche_tag}}
            </div>
            {{og_image_html}}
            {{content}}
            {{related_html}}
        </article>
    </main>
    <footer>
        <p>&copy; {{year}} {{site_name}} &mdash; <a href="/rss.xml">RSS</a> · <a href="/sitemap.xml">Sitemap</a> · <a href="/all.html">Все статьи</a></p>
    </footer>
</body>
</html>"""


def _reading_time(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    words = len(text.split())
    minutes = max(1, round(words / 200))
    endings = {1: "минуту", 2: "минуты", 3: "минуты", 4: "минуты"}
    ending = endings.get(minutes % 10, "минут") if minutes % 100 not in (11, 12, 13, 14) else "минут"
    return f"{minutes} {ending} чтения"


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
        result = result.replace("{{%s}}" % k, str(v))
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


def _build_card(img_html: str, slug: str, title: str, date: str, niche: str, snippet: str, reading_time: str) -> str:
    niche_tag = '<a href="/niche-%s.html" class="niche-tag">%s</a>' % (niche, NICHE_NAMES.get(niche, niche)) if niche else ""
    return (
        '<div class="article-card" data-niche="%s">'
        '%s'
        '<div class="card-body">'
        '<div class="meta">%s %s · %s</div>'
        '<h2><a href="%s.html">%s</a></h2>'
        "<p>%s...</p></div></div>"
    ) % (niche, img_html, niche_tag, date, reading_time, slug, title, snippet)


def _niche_page_html(niche_key: str, articles: list[dict]) -> str:
    niche_name = NICHE_NAMES.get(niche_key, niche_key)
    cards = []
    for art in articles:
        img = '<div class="card-img"><img src="%s" alt="" loading="lazy"/></div>' % art["og_image"] if art.get("og_image") else ""
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        cards.append(_build_card(img, art["slug"], art["title"], art["date"], art.get("niche", ""), snippet, art["reading_time"]))
    return '<div class="page-header"><h2>%s</h2><p>%d статей</p></div><div class="article-list">%s</div>' % (
        niche_name, len(cards), "\n".join(cards)
    )


def _make_jsonld(title: str, description: str, url: str, image: str, date: str, site_name: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "image": image,
        "datePublished": date,
        "author": {"@type": "Organization", "name": site_name},
        "publisher": {"@type": "Organization", "name": site_name, "logo": {"@type": "ImageObject", "url": ""}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


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
            '<div style="margin-bottom:24px"><img src="%s" alt="%s" style="width:100%%;max-width:720px;border-radius:8px" loading="lazy"></div>'
        ) % (og_image, clean_title or title) if og_image else ""

        niche_tag = ""
        if niche and niche in NICHE_NAMES:
            niche_tag = '<a href="/niche-%s.html" class="niche-tag">%s</a>' % (niche, NICHE_NAMES[niche])

        reading_time = _reading_time(content)

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
            "reading_time": reading_time,
        })

    nav_links = "".join(
        '<a href="/niche-%s.html">%s</a>' % (key, name)
        for key, name in NICHE_NAMES.items()
    )

    for i, art in enumerate(articles):
        related = _find_related(articles, i, count=3)
        related_html = ""
        if related:
            links = "\n".join('<a href="%s.html">%s</a>' % (r["slug"], r["title"]) for r in related)
            related_html = '<div class="related"><h3>📖 Читайте также</h3>%s</div>' % links

        url = "%s/%s.html" % (SITE_URL, art["slug"]) if SITE_URL else "/%s.html" % art["slug"]
        niche_url = "/niche-%s.html" % art["niche"] if art["niche"] else "/"
        niche_name = NICHE_NAMES.get(art["niche"], art["niche"]) if art["niche"] else ""

        jsonld = _make_jsonld(art["title"], art["description"], url, art["og_image"], art["iso_date"], SITE_NAME)

        page = _render(
            ARTICLE_TEMPLATE,
            css=CSS,
            title=art["title"],
            description=art["description"],
            keywords=art["keywords"],
            url=url,
            og_image=art["og_image"],
            site_name=SITE_NAME,
            date=art["date"],
            reading_time=art["reading_time"],
            og_image_html=art["og_image_html"],
            niche_tag=art["niche_tag"],
            niche_url=niche_url,
            niche_name=niche_name,
            content=art["content"],
            related_html=related_html,
            year=art["year"],
            nav_links=nav_links,
            jsonld=jsonld,
        )
        (SITE_DIR / ("%s.html" % art["slug"])).write_text(page, encoding="utf-8")

    logger.info("  Generated %d article pages" % len(articles))

    all_cards = []
    for art in articles:
        img = '<div class="card-img"><img src="%s" alt="" loading="lazy"/></div>' % art["og_image"] if art.get("og_image") else ""
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        all_cards.append(_build_card(img, art["slug"], art["title"], art["date"], art["niche"], snippet, art["reading_time"]))

    og_url = SITE_URL + "/all.html" if SITE_URL else "/all.html"
    jsonld_all = _make_jsonld("Все статьи — " + SITE_NAME, SITE_DESCRIPTION, og_url, "", datetime.now().strftime("%Y-%m-%d"), SITE_NAME)
    all_page = _render(
        HEAD,
        css=CSS,
        title="Все статьи — " + SITE_NAME,
        description=SITE_DESCRIPTION,
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        og_title="Все статьи — " + SITE_NAME,
        og_description=SITE_DESCRIPTION,
        og_url=og_url,
        og_image="",
        nav_links=nav_links,
        jsonld=jsonld_all,
        content='<div class="page-header"><h2>Все статьи</h2><p>%d статей</p></div><div class="article-list">%s</div>' % (len(all_cards), "\n".join(all_cards)),
        year=str(datetime.now().year),
    )
    (SITE_DIR / "all.html").write_text(all_page, encoding="utf-8")
    logger.info("  Generated: all.html (%d articles)" % len(all_cards))

    niche_articles: dict[str, list[dict]] = {}
    for art in articles:
        n = art.get("niche", "")
        if not n or n not in NICHE_NAMES:
            n = "технологии"
        niche_articles.setdefault(n, []).append(art)

    for niche_key, niche_arts in niche_articles.items():
        niche_content = _niche_page_html(niche_key, niche_arts)
        niche_name = NICHE_NAMES.get(niche_key, niche_key)
        og_url_niche = "%s/niche-%s.html" % (SITE_URL, niche_key) if SITE_URL else "/niche-%s.html" % niche_key
        jsonld_niche = _make_jsonld(niche_name + " — " + SITE_NAME, "Статьи по теме «%s»" % niche_name, og_url_niche, "", datetime.now().strftime("%Y-%m-%d"), SITE_NAME)
        page = _render(
            HEAD,
            css=CSS,
            title=niche_name + " — " + SITE_NAME,
            description="Статьи по теме «%s»" % niche_name,
            site_name=SITE_NAME,
            site_description=SITE_DESCRIPTION,
            og_title=niche_name + " — " + SITE_NAME,
            og_description="Статьи по теме «%s»" % niche_name,
            og_url=og_url_niche,
            og_image="",
            nav_links=nav_links,
            jsonld=jsonld_niche,
            content=niche_content,
            year=str(datetime.now().year),
        )
        (SITE_DIR / ("niche-%s.html" % niche_key)).write_text(page, encoding="utf-8")

    logger.info("  Generated %d niche category pages" % len(niche_articles))

    index_cards = []
    for art in articles[:20]:
        img = '<div class="card-img"><img src="%s" alt="" loading="lazy"/></div>' % art["og_image"] if art.get("og_image") else ""
        snippet = re.sub(r"<[^>]+>", "", art["content"])
        snippet = re.sub(r"\s+", " ", snippet).strip()[:150]
        index_cards.append(_build_card(img, art["slug"], art["title"], art["date"], art["niche"], snippet, art["reading_time"]))

    index_all_link = '<div class="pagination"><a href="/all.html">Все статьи →</a></div>' if len(articles) > 20 else ""
    og_url_index = SITE_URL + "/" if SITE_URL else "/"
    jsonld_index = _make_jsonld(SITE_NAME, SITE_DESCRIPTION, og_url_index, "", datetime.now().strftime("%Y-%m-%d"), SITE_NAME)

    index_page = _render(
        HEAD,
        css=CSS,
        title=SITE_NAME,
        description=SITE_DESCRIPTION,
        site_name=SITE_NAME,
        site_description=SITE_DESCRIPTION,
        og_title=SITE_NAME,
        og_description=SITE_DESCRIPTION,
        og_url=og_url_index,
        og_image="",
        nav_links=nav_links,
        jsonld=jsonld_index,
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
