""""""
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NICHES = [
    "искусственный интеллект",
    "технологии",
    "авто",
    "здоровье",
    "финансы",
    "бизнес",
    "образование",
    "спорт",
    "кино",
    "путешествия",
]

TOP_VK_GROUPS = {
    "искусственный интеллект": [
        ("Нейросети и ИИ", -228167053, "neuroseti_i_i"),
        ("AI | Нейросети | Искусственный интеллект", -204677466, "ai_news_media"),
        ("Data Science | ИИ", -212806818, "data_science_ai"),
    ],
    "технологии": [
        ("Технологии | Гаджеты | Инновации", -212336273, "techno_gadgets"),
        ("Hi-Tech", -212043433, "hitech_news_ru"),
        ("IT Новости", -215732496, "it_news_media"),
    ],
    "авто": [
        ("Автомобили | Новости", -212922577, "auto_news_media"),
        ("Авто Мир", -213386630, "auto_world_rus"),
    ],
    "здоровье": [
        ("Здоровье | Медицина", -217207338, "health_medicine_ru"),
        ("Фитнес | ЗОЖ", -218515651, "fitness_zozh"),
    ],
    "финансы": [
        ("Финансы | Инвестиции", -214108056, "finance_invest_ru"),
        ("Экономика и финансы", -213397839, "economy_finance_ru"),
    ],
    "бизнес": [
        ("Бизнес | Стартапы | Предпринимательство", -218073584, "business_startup_ru"),
        ("Маркетинг и Бизнес", -210841305, "marketing_business_ru"),
    ],
    "образование": [
        ("Образование | Саморазвитие", -218069128, "education_selfdev"),
        ("Учеба | Курсы", -213270576, "study_courses_ru"),
    ],
    "спорт": [
        ("Спорт | Новости", -213252532, "sport_news_media"),
        ("Фитнес | Тренировки", -215897862, "fitness_workout_ru"),
    ],
    "кино": [
        ("Кино | Фильмы | Сериалы", -211243628, "kino_media_ru"),
        ("КиноМир", -215354896, "kino_mir_ru"),
    ],
    "путешествия": [
        ("Путешествия | Туризм", -214465963, "travel_tourism_ru"),
        ("Туризм и отдых", -213694619, "tourism_rest_ru"),
    ],
}

VK_API = "https://api.vk.com/method"
VK_VERSION = "5.199"


def _vk_request(method: str, params: dict, token: str) -> dict | None:
    params["access_token"] = token
    params["v"] = VK_VERSION
    try:
        resp = requests.post(f"{VK_API}/{method}", data=params, timeout=20)
        data = resp.json()
        if "error" in data:
            logger.warning("VK API error %s: %s", method, data["error"].get("error_msg", ""))
            return None
        return data.get("response")
    except Exception as e:
        logger.warning("VK request failed %s: %s", method, e)
        return None


def get_top_groups(niche: str) -> list[dict]:
    groups = TOP_VK_GROUPS.get(niche, [])
    return [{"name": g[0], "id": -g[1], "owner_id": g[1], "screen_name": g[2], "niche": niche} for g in groups]


def get_vk_group_stats(group_id: int, token: str) -> dict | None:
    resp = _vk_request("groups.getById", {"group_id": group_id, "fields": "members_count,activity,status,description"}, token)
    if resp and len(resp) > 0:
        g = resp[0]
        return {"name": g.get("name", ""), "members": g.get("members_count", 0), "status": g.get("status", ""), "description": g.get("description", "")[:300]}
    return None


def analyze_vk_wall(owner_id: int, token: str, days: int = 30) -> dict:
    posts = []
    cutoff = datetime.now() - timedelta(days=days)
    resp = _vk_request("wall.get", {"owner_id": -owner_id, "count": 100}, token)
    if not resp:
        return {"error": "no data"}

    for post in resp.get("items", []):
        ts = datetime.fromtimestamp(post["date"])
        if ts < cutoff:
            continue
        text = post.get("text", "")
        stats = {
            "date": ts.isoformat(),
            "text": text,
            "likes": post.get("likes", {}).get("count", 0),
            "comments": post.get("comments", {}).get("count", 0),
            "reposts": post.get("reposts", {}).get("count", 0),
            "views": post.get("views", {}).get("count", 0) if "views" in post else 0,
            "has_image": 1 if "attachments" in post and any(a["type"] == "photo" for a in post["attachments"]) else 0,
            "has_link": 1 if "attachments" in post and any(a["type"] == "link" for a in post["attachments"]) else 0,
            "has_poll": 1 if "attachments" in post and any(a["type"] == "poll" for a in post["attachments"]) else 0,
        }
        posts.append(stats)

    if not posts:
        return {"error": "no posts in period"}

    total = len(posts)
    avg_likes = sum(p["likes"] for p in posts) / total
    avg_comments = sum(p["comments"] for p in posts) / total
    avg_reposts = sum(p["reposts"] for p in posts) / total
    avg_views = sum(p["views"] for p in posts) / total if posts[0]["views"] else 0
    avg_engagement = (avg_likes + avg_comments + avg_reposts) / max(avg_views, 1) * 100 if avg_views else 0

    all_text = " ".join(p["text"] for p in posts)
    words = re.findall(r"\w+", all_text.lower())
    top_words = Counter(w for w in words if len(w) > 3).most_common(20)
    hashtags = re.findall(r"#\w+", all_text)
    top_hashtags = Counter(h.strip().lower() for h in hashtags).most_common(10)
    avg_len = sum(len(p["text"]) for p in posts) / total
    img_ratio = sum(p["has_image"] for p in posts) / total * 100
    poll_ratio = sum(p["has_poll"] for p in posts) / total * 100
    emoji_count = sum(len(re.findall(r"[\U0001F600-\U0001FFFF]", p["text"])) for p in posts)
    avg_emoji = emoji_count / total

    return {
        "total_posts": total,
        "days_analyzed": days,
        "posts_per_day": round(total / days, 1),
        "avg_likes": round(avg_likes, 1),
        "avg_comments": round(avg_comments, 1),
        "avg_reposts": round(avg_reposts, 1),
        "avg_views": round(avg_views, 1) if avg_views else None,
        "avg_engagement_pct": round(avg_engagement, 3) if avg_views else None,
        "avg_text_len": round(avg_len, 0),
        "img_pct": round(img_ratio, 0),
        "poll_pct": round(poll_ratio, 0),
        "avg_emoji_per_post": round(avg_emoji, 1),
        "top_words": top_words[:10],
        "top_hashtags": top_hashtags[:10],
        "engagement_score": round(avg_likes * 0.4 + avg_comments * 0.4 + avg_reposts * 0.2, 1),
    }


def run_vk_analysis(token: str, output_path: Path = Path("data/competitor_analysis.json")):
    if not token:
        logger.error("VK_ACCESS_TOKEN not set")
        return

    report = {
        "generated_at": datetime.now().isoformat(),
        "niches": {},
    }

    for niche in NICHES:
        logger.info("Analyzing niche: %s", niche)
        groups = get_top_groups(niche)
        niche_data = {"groups": []}

        for g in groups:
            logger.info("  VK group: %s", g["name"])
            wall = analyze_vk_wall(g["owner_id"], token, days=14)
            stats = get_vk_group_stats(-g["owner_id"], token)
            members = stats.get("members", 0) if stats else 0
            niche_data["groups"].append({
                "name": g["name"],
                "screen_name": g["screen_name"],
                "members": members,
                "stats": stats or {},
                "wall_analysis": wall,
            })

        report["niches"][niche] = niche_data

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Competitor analysis saved to %s", output_path)


def generate_recommendations(analysis_path: Path = Path("data/competitor_analysis.json")) -> str:
    if not analysis_path.exists():
        return "Анализ не проведён."

    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    lines = ["# Анализ конкурентов Runet", "", "Сгенерирован: %s" % data.get("generated_at", ""), ""]

    for niche, ndata in data.get("niches", {}).items():
        lines.append("---")
        lines.append("## %s" % niche)
        lines.append("")
        for g in ndata.get("groups", []):
            w = g.get("wall_analysis", {})
            if "error" in w:
                lines.append("- %s: нет данных" % g["name"])
                continue
            lines.append("- %s (подп.: %s)" % (g["name"], g["members"]))
            lines.append("  - Постов/день: %.1f" % w.get("posts_per_day", 0))
            lines.append("  - Вовлечение: %.1f лайков, %.1f комм, %.1f репостов" % (
                w.get("avg_likes", 0), w.get("avg_comments", 0), w.get("avg_reposts", 0)))
            if w.get("avg_views"):
                lines.append("  - Просмотров/пост: %.0f" % w["avg_views"])
            if w.get("avg_engagement_pct"):
                lines.append("  - ER: %.2f%%" % w["avg_engagement_pct"])
            lines.append("  - Длина текста: %.0f символов" % w.get("avg_text_len", 0))
            lines.append("  - Картинки: %.0f%% постов" % w.get("img_pct", 0))
            lines.append("  - Опросы: %.0f%% постов" % w.get("poll_pct", 0))
            if w.get("top_hashtags"):
                lines.append("  - Хештеги: %s" % ", ".join("#" + h for h, _ in w["top_hashtags"][:5]))
            lines.append("")

    lines.append("---")
    lines.append("## Best Practices (на основе анализа)")
    for bp in _best_practices():
        lines.append("")
        lines.extend(bp)

    return "\n".join(lines)


def _best_practices() -> list[list[str]]:
    return [
        ["1. Частота: 3-5 постов/день для высокого охвата"],
        ["2. Длина: 800-2000 символов - оптимальный баланс"],
        ["3. Картинки: 80%+ постов должны содержать изображение"],
        ["4. Опросы: 10-15% постов с опросами повышают вовлечение"],
        ["5. Emoji: умеренно, 3-7 на пост для акцентов"],
        ["6. Вопросы: каждый пост заканчивать вопросом к аудитории"],
        ["7. Хештеги: 3-5 релевантных хештега на пост"],
        ["8. Время: пик активности 12:00-15:00 и 19:00-22:00 MSK"],
    ]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    token = os.getenv("VK_ACCESS_TOKEN", "")
    if "--report" in sys.argv:
        print(generate_recommendations())
    else:
        run_vk_analysis(token)
        print(generate_recommendations())
