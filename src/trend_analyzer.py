import asyncio
import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

PREDEFINED_NICHES = [
    "искусственный интеллект",
    "авто",
    "технологии",
    "здоровье",
    "финансы",
    "бизнес",
    "образование",
    "спорт",
    "кино",
    "путешествия",
]

ROTATION_FILE = Path("data") / "niche_rotation_index.txt"


def _read_rotation_index() -> int:
    if ROTATION_FILE.exists():
        try:
            return int(ROTATION_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return 0
    return 0


def _save_rotation_index(idx: int):
    ROTATION_FILE.write_text(str(idx), encoding="utf-8")


def _rotate_fallback() -> str:
    idx = _read_rotation_index()
    niche = PREDEFINED_NICHES[idx % len(PREDEFINED_NICHES)]
    _save_rotation_index((idx + 1) % len(PREDEFINED_NICHES))
    logger.info(f"Fallback rotation: {niche}")
    return niche


def _map_to_predefined_niche(raw: str) -> str | None:
    """Map any niche string to the closest predefined niche."""
    raw_lower = raw.strip().lower().rstrip(".!")
    if raw_lower in PREDEFINED_NICHES:
        return raw_lower
    mapping = {
        "ии": "искусственный интеллект",
        "ai": "искусственный интеллект",
        "нейросети": "искусственный интеллект",
        "гпт": "искусственный интеллект",
        "электромобили": "авто",
        "автомобили": "авто",
        "криптовалюта": "финансы",
        "крипто": "финансы",
        "инвестиции": "финансы",
        "медицина": "здоровье",
        "фитнес": "спорт",
        "спортзал": "спорт",
        "киберспорт": "спорт",
        "путешествие": "путешествия",
        "туризм": "путешествия",
        "образование": "образование",
        "кино": "кино",
        "фильмы": "кино",
        "сериалы": "кино",
        "здоровое питание": "здоровье",
        "диета": "здоровье",
        "бизнес": "бизнес",
        "стартап": "бизнес",
        "маркетинг": "бизнес",
        "цифровые технологии": "технологии",
        "гаджеты": "технологии",
        "инновации": "технологии",
    }
    return mapping.get(raw_lower)


async def _from_google_trends() -> str | None:
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ru-RU", tz=180, timeout=10)

        trending = pytrends.trending_searches(pn="russia")
        if not trending.empty:
            niche = str(trending.iloc[0, 0]).strip().lower()
            if niche and len(niche) > 3:
                logger.info(f"Google Trends (top trending): {niche}")
                return niche

        categories = [
            "искусственный интеллект",
            "нейросети",
            "авто",
            "криптовалюта",
            "здоровье",
            "финансы",
            "спорт",
            "кино",
            "бизнес",
            "образование",
        ]
        pytrends.build_payload(
            kw_list=categories, timeframe="now 7-d", geo="RU", gprop=""
        )
        df = pytrends.interest_over_time()
        if df is not None and not df.empty:
            df = df.drop(columns=["isPartial"], errors="ignore")
            means = df[categories].mean()
            top = means.idxmax()
            logger.info(f"Google Trends (category peak): {top}")
            return top

    except Exception as e:
        logger.warning(f"Google Trends failed: {e}")

    return None


async def _from_post_history() -> str | None:
    """Pick best niche from post engagement history (0 API calls).

    Only returns a niche if there are records with actual engagement scores.
    """
    history_path = Path("data") / "post_history.json"
    if not history_path.exists():
        return None

    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return None

    niche_scores: dict[str, list[float]] = {}
    for record in history:
        niche = record.get("niche", "")
        if not niche:
            continue
        score = record.get("score")
        if score is None:
            continue
        niche_scores.setdefault(niche, []).append(float(score))

    if not niche_scores:
        logger.info("Post history: no scored posts yet, skipping")
        return None

    best_niche = max(niche_scores, key=lambda n: sum(niche_scores[n]) / len(niche_scores[n]))
    avg_score = sum(niche_scores[best_niche]) / len(niche_scores[best_niche])
    logger.info(f"Post history best niche: {best_niche} (avg score: {avg_score:.2f})")
    return best_niche


async def detect_trending_niche(
    client: DeepSeekClient,
    base_niche: str = "",
) -> str:
    logger.info("Analyzing trending niches...")

    # 1. Google Trends (free)
    niche = await _from_google_trends()
    if niche:
        mapped = _map_to_predefined_niche(niche)
        if mapped:
            logger.info(f"Google Trends → {niche} → mapped to '{mapped}'")
            return mapped
        logger.info(f"Google Trends returned '{niche}' — no mapping, skipping")

    # 2. Post history analysis (only if scored posts exist)
    niche = await _from_post_history()
    if niche:
        return niche

    # 3. DeepSeek trend analysis (constrained to predefined niches)
    niche = await _from_deepseek(client, base_niche)
    if niche:
        return niche

    # 4. Fallback rotation (cycles through all predefined niches)
    return _rotate_fallback()


async def _from_deepseek(client: DeepSeekClient, base_niche: str = "") -> str | None:
    """Ask DeepSeek for the hottest niche right now, constrained to predefined list."""
    current_month = datetime.now().strftime("%B")
    predefined_list = "\n".join(f"- {n}" for n in PREDEFINED_NICHES)
    prompt = (
        f"Какая ниша из списка ниже сейчас САМАЯ ГОРЯЧАЯ и трендовая именно сейчас "
        f"({current_month} {datetime.now().year}, Россия/СНГ)?\n\n"
        f"{predefined_list}\n\n"
        f"Учитывай: сезонность, мировые тренды, хайп, коммерческую привлекательность.\n\n"
        f"Верни ТОЛЬКО название ниши из списка, ровно одну строку. Ничего другого."
    )
    try:
        result = await client.call(
            prompt=prompt,
            system_prompt="Ты — аналитик трендов. Отвечай только названием ниши из предложенного списка.",
            temperature=0.4,
            max_tokens=50,
        )
        mapped = _map_to_predefined_niche(result.strip())
        if mapped:
            logger.info(f"DeepSeek trend: '{mapped}'")
            return mapped
        logger.warning(f"DeepSeek returned unmappable niche: '{result.strip()}'")
    except Exception as e:
        logger.warning(f"DeepSeek trend analysis failed: {e}")
    return None



