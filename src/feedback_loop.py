"""
Feedback loop module for AI Content Farm.
Collects metrics, scores posts, analyzes patterns, and improves generation prompts.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from uuid import uuid4

from src.state_store import atomic_write_json, read_json

logger = logging.getLogger(__name__)

POST_HISTORY_PATH = Path("data") / "post_history.json"
LEARNED_PATTERNS_PATH = Path("data") / "learned_patterns.json"
PROMPT_PATH = Path("prompts") / "write_article.prompter"

WEIGHT_VIEWS = 0.4
WEIGHT_REACTIONS = 0.3
WEIGHT_COMMENTS = 0.3
VK_API_VERSION = "5.199"
VK_BATCH_SIZE = 100


def _load_history() -> list[dict]:
    return read_json(POST_HISTORY_PATH, [], critical=True)


def _save_history(history: list[dict]):
    atomic_write_json(POST_HISTORY_PATH, history)


def _load_patterns() -> dict:
    if LEARNED_PATTERNS_PATH.exists():
        try:
            return json.loads(LEARNED_PATTERNS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            return {"patterns": "", "recommendations": [], "last_updated": None, "version": 0}
    return {"patterns": "", "recommendations": [], "last_updated": None, "version": 0}


def _save_patterns(patterns: dict):
    atomic_write_json(LEARNED_PATTERNS_PATH, patterns)


def record_publication(
    topic: str,
    title: str,
    niche: str,
    tg_message_id: int | None = None,
    vk_post_id: int | None = None,
    vk_owner_id: str | None = None,
    ok_post_id: str | None = None,
    ab_variant: str | None = None,
    publication_id: str | None = None,
) -> dict:
    history = _load_history()
    record = {
        "publication_id": publication_id or str(uuid4()),
        "topic": topic,
        "title": title,
        "niche": niche,
        "published_at": datetime.now().isoformat(),
        "platforms": {},
        "score": None,
    }
    if ab_variant in {"A", "B"}:
        record["ab_variant"] = ab_variant
    if tg_message_id is not None:
        record["platforms"]["telegram"] = {
            "message_id": tg_message_id,
            "views": None,
            "reactions": None,
            "comments": None,
        }
    if vk_post_id is not None:
        record["platforms"]["vk"] = {
            "post_id": vk_post_id,
            "owner_id": vk_owner_id or "",
            "format": "A",
            "views": None,
            "likes": None,
            "comments": None,
            "reposts": None,
        }
    if ok_post_id is not None:
        record["platforms"]["ok"] = {
            "post_id": ok_post_id,
            "views": None,
            "likes": None,
            "comments": None,
            "reposts": None,
        }
    history.append(record)
    _save_history(history)
    logger.info(f"Recorded publication: {title}")
    return record


def _normalize_vk_owner_id(group_id: str) -> str:
    numeric_id = str(group_id).strip()
    for prefix in ("club", "public"):
        if numeric_id.startswith(prefix):
            numeric_id = numeric_id[len(prefix):]
    return numeric_id if numeric_id.startswith("-") else f"-{numeric_id}"


def _vk_post_refs(history: list[dict], fallback_owner_id: str) -> list[str]:
    refs = []
    for record in history:
        vk_data = record.get("platforms", {}).get("vk") or {}
        post_id = vk_data.get("post_id")
        if post_id is None:
            continue
        owner_id = str(vk_data.get("owner_id") or fallback_owner_id)
        refs.append(f"{owner_id}_{post_id}")
    return list(dict.fromkeys(refs))


def _chunks(items: list[str], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _fetch_vk_metrics(
    history: list[dict],
    access_token: str,
    group_id: str,
    http_post: Callable,
) -> dict[str, dict]:
    """Fetch exact saved posts instead of scanning a potentially restricted wall."""
    fallback_owner_id = _normalize_vk_owner_id(group_id)
    refs = _vk_post_refs(history, fallback_owner_id)
    metrics: dict[str, dict] = {}

    for batch_number, batch in enumerate(_chunks(refs, VK_BATCH_SIZE), 1):
        try:
            response = http_post(
                "https://api.vk.com/method/wall.getById",
                data={
                    "access_token": access_token,
                    "v": VK_API_VERSION,
                    "posts": ",".join(batch),
                    "extended": 0,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("VK wall.getById batch %d failed: %s", batch_number, exc)
            continue

        if "error" in payload:
            error = payload["error"]
            error_code = error.get("error_code", "?")
            if error_code == 27:
                logger.error(
                    "VK analytics requires a user/service token. The configured "
                    "token is a group token and cannot read post metrics. Set "
                    "VK_ANALYTICS_TOKEN separately."
                )
            else:
                logger.warning(
                    "VK wall.getById error %s: %s",
                    error_code,
                    error.get("error_msg", "unknown error"),
                )
            continue

        posts = payload.get("response", [])
        if isinstance(posts, dict):
            posts = posts.get("items", [])

        for post in posts:
            post_id = post.get("id")
            owner_id = post.get("owner_id")
            if post_id is None or owner_id is None:
                continue
            metrics[f"{owner_id}_{post_id}"] = {
                "views": (post.get("views") or {}).get("count", 0),
                "likes": (post.get("likes") or {}).get("count", 0),
                "comments": (post.get("comments") or {}).get("count", 0),
                "reposts": (post.get("reposts") or {}).get("count", 0),
            }

    return metrics


def _apply_vk_metrics(
    history: list[dict],
    metrics: dict[str, dict],
    fallback_owner_id: str,
    collected_at: datetime | None = None,
) -> tuple[int, int]:
    now = collected_at or datetime.now()
    matched = 0
    changed = 0

    for record in history:
        vk_data = record.get("platforms", {}).get("vk")
        if not vk_data or vk_data.get("post_id") is None:
            continue

        owner_id = str(vk_data.get("owner_id") or fallback_owner_id)
        ref = f"{owner_id}_{vk_data['post_id']}"
        stats = metrics.get(ref)
        if stats is None:
            continue
        matched += 1

        previous = {key: vk_data.get(key) for key in stats}
        vk_data.update(stats)
        vk_data["metrics_collected_at"] = now.isoformat()

        try:
            published_at = datetime.fromisoformat(record["published_at"])
            age_hours = max((now - published_at).total_seconds() / 3600, 0)
        except (KeyError, TypeError, ValueError):
            age_hours = 0

        snapshot = {**stats, "collected_at": now.isoformat()}
        snapshots = vk_data.setdefault("metric_snapshots", {})
        snapshots["latest"] = snapshot
        if age_hours < 24:
            snapshots.setdefault("initial", snapshot)
        elif age_hours < 72:
            snapshots.setdefault("24h", snapshot)
        else:
            snapshots.setdefault("72h", snapshot)

        if previous != stats:
            changed += 1

    return matched, changed


async def collect_metrics(vk_access_token: str = "", vk_group_id: str = "") -> list[dict]:
    import requests as sync_requests

    history = _load_history()
    if not history:
        logger.info("No posts in history to collect metrics for.")
        return history

    if vk_access_token and vk_group_id:
        owner_id = _normalize_vk_owner_id(vk_group_id)
        post_metrics = _fetch_vk_metrics(
            history, vk_access_token, vk_group_id, sync_requests.post
        )
        matched, changed = _apply_vk_metrics(history, post_metrics, owner_id)
        logger.info(
            "VK metrics: requested %d posts, matched %d, changed %d",
            len(_vk_post_refs(history, owner_id)),
            matched,
            changed,
        )
        if matched:
            _save_history(history)
        elif _vk_post_refs(history, owner_id):
            logger.warning(
                "VK returned no matching posts. Check token access, VK_GROUP_ID "
                "and owner_id values stored in post_history.json."
            )

    # --- Telegram: Bot API can't fetch per-message stats for channels ---
    # Placeholder for future extension (e.g. via Telegram API or parsing)

    return history


def score_posts(history: list[dict] | None = None, days_back: int = 30) -> list[tuple[dict, float]]:
    if history is None:
        history = _load_history()

    cutoff = datetime.now() - timedelta(days=days_back)
    scored = []

    for record in history:
        try:
            published_at = datetime.fromisoformat(record["published_at"])
        except (ValueError, TypeError):
            continue
        if published_at < cutoff:
            continue

        lifetime = max((datetime.now() - published_at).total_seconds() / 3600, 1)

        views = 0
        reactions = 0
        comments = 0

        for pf, data in record.get("platforms", {}).items():
            if pf == "telegram":
                views += data.get("views", 0) or 0
                reactions += data.get("reactions", 0) or 0
                comments += data.get("comments", 0) or 0
            elif pf == "vk":
                views += data.get("views", 0) or 0
                reactions += data.get("likes", 0) or 0
                comments += data.get("comments", 0) or 0

        # Do not teach the generator from publications for which no platform
        # has returned real metrics yet.
        has_metrics = any(
            data.get("views") is not None
            for data in record.get("platforms", {}).values()
        )
        if not has_metrics:
            record["score"] = None
            continue

        score = (
            views * WEIGHT_VIEWS
            + reactions * WEIGHT_REACTIONS
            + comments * WEIGHT_COMMENTS
        ) / lifetime

        record["score"] = round(score, 4)
        scored.append((record, round(score, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    _save_history(history)
    return scored


def get_top_posts(n: int = 3, days_back: int = 30) -> list[tuple[dict, float]]:
    scored = score_posts(days_back=days_back)
    return scored[:n]


def get_recommendations() -> list[str]:
    patterns = _load_patterns()
    return patterns.get("recommendations", [])


def inject_recommendations(system_prompt: str) -> str:
    recs = get_recommendations()
    if not recs:
        return system_prompt
    base = system_prompt.strip() or "Ты — автор контент-фермы. Пиши интересные и полезные статьи."
    rec_block = "\n".join(f"- {r}" for r in recs)
    extra = (
        "\n\nУчти следующие рекомендации на основе анализа успешных постов:\n"
        f"{rec_block}"
    )
    return base + extra


async def analyze_top_posts(client, top_posts: list[tuple[dict, float]]) -> dict | None:
    if not top_posts:
        logger.warning("No top posts to analyze.")
        return None

    posts_text = ""
    for i, (record, score) in enumerate(top_posts, 1):
        title = record.get("title", record.get("topic", "Untitled"))
        posts_text += f"\n--- Пост {i} (score: {score:.2f}) ---\n"
        posts_text += f"Заголовок: {title}\n"
        posts_text += f"Тема: {record.get('topic', '')}\n"
        posts_text += f"Ниша: {record.get('niche', '')}\n"
        posts_text += f"Опубликован: {record.get('published_at', '')}\n"
        for pf, data in record.get("platforms", {}).items():
            metrics = ", ".join(f"{k}: {v}" for k, v in data.items() if v is not None)
            if metrics:
                posts_text += f"Метрики ({pf}): {metrics}\n"

    system_prompt = (
        "Ты — аналитик контент-стратегии. "
        "Анализируй успешные посты и выделяй общие паттерны."
    )
    user_prompt = (
        f"Ниже представлены топ-{len(top_posts)} самых успешных постов контент-фермы.\n\n"
        f"{posts_text}\n\n"
        "Проанализируй их и выдели ОБЩИЕ черты:\n"
        "1. Что общего в заголовках? (структура, длина, тон, вопросы/цифры/эмодзи)\n"
        "2. Что общего в структуре статей? (вступление, списки, выводы)\n"
        "3. Какая тональность сработала лучше? (экспертная, разговорная, провокационная)\n"
        "4. Какие темы/ключевые слова повторяются?\n\n"
        "Сформулируй 3-5 конкретных, практических рекомендаций для будущих статей. "
        "Рекомендации должны быть чёткими и применимыми (например: "
        "\"используй заголовки-вопросы\", \"добавляй эмодзи в первый абзац\", "
        "\"избегай цифр в начале заголовка\").\n\n"
        "Верни результат в JSON формате:\n"
        "{\n"
        '  "patterns": "общий анализ паттернов (2-3 предложения)",\n'
        '  "recommendations": ["рекомендация 1", "рекомендация 2", ...]\n'
        "}"
    )

    try:
        result = await client.call_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000,
        )
        patterns_text = result.get("patterns", "")
        recommendations = result.get("recommendations", [])
        logger.info(f"Pattern analysis complete. Recommendations: {recommendations}")

        pat = _load_patterns()
        pat["patterns"] = patterns_text
        pat["recommendations"] = recommendations
        pat["last_updated"] = datetime.now().isoformat()
        pat["version"] = pat.get("version", 0) + 1
        _save_patterns(pat)

        return result
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        return None


def get_patterns_summary() -> str:
    pat = _load_patterns()
    lines = []
    if pat.get("recommendations"):
        lines.append("📊 Рекомендации на основе успешных постов:")
        for r in pat["recommendations"]:
            lines.append(f"  • {r}")
    if pat.get("patterns"):
        lines.append(f"\n📝 Анализ: {pat['patterns']}")
    if pat.get("last_updated"):
        lines.append(f"\n🔄 Обновлено: {pat['last_updated']}")
    return "\n".join(lines) if lines else "Нет накопленных рекомендаций."


async def run_feedback_loop(
    client,
    vk_access_token: str = "",
    vk_group_id: str = "",
    top_n: int = 3,
    days_back: int = 30,
) -> dict | None:
    logger.info("=" * 60)
    logger.info("FEEDBACK LOOP — сбор метрик, анализ, обучение")
    logger.info("=" * 60)

    await collect_metrics(vk_access_token=vk_access_token, vk_group_id=vk_group_id)

    top_posts = get_top_posts(n=top_n, days_back=days_back)
    if not top_posts:
        logger.info("No scored posts available for analysis.")
        return None

    logger.info(f"Top-{len(top_posts)} posts selected for analysis:")
    for i, (rec, sc) in enumerate(top_posts, 1):
        logger.info(f"  {i}. {rec.get('title', rec.get('topic', '?'))} — score: {sc}")

    result = await analyze_top_posts(client, top_posts)

    if result:
        logger.info("Feedback loop complete. Recommendations saved.")
        logger.info(get_patterns_summary())
    else:
        logger.info("Feedback loop finished without new recommendations.")

    return result


if __name__ == "__main__":
    import argparse
    import asyncio
    import os
    import sys

    from dotenv import load_dotenv

    sys.path.insert(0, str(Path(__file__).parent.parent))
    load_dotenv()

    parser = argparse.ArgumentParser(description="AI Content Farm — Feedback Loop")
    parser.add_argument("--top", type=int, default=3, help="Number of top posts to analyze")
    parser.add_argument("--days", type=int, default=30, help="Days back to consider")
    parser.add_argument("--status", action="store_true", help="Show current recommendations")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("logs/feedback.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    if args.status:
        print(get_patterns_summary())
        sys.exit(0)

    from src.deepseek_client import DeepSeekClient

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY not found in .env")
        sys.exit(1)

    vk_token = os.getenv("VK_ANALYTICS_TOKEN") or os.getenv("VK_ACCESS_TOKEN", "")
    vk_group = os.getenv("VK_GROUP_ID", "")

    client = DeepSeekClient(api_key=api_key)
    asyncio.run(run_feedback_loop(
        client=client,
        vk_access_token=vk_token,
        vk_group_id=vk_group,
        top_n=args.top,
        days_back=args.days,
    ))
