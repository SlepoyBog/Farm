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

FALLBACK_NICHES = [
    "искусственный интеллект",
    "авто",
    "здоровье",
    "финансы",
    "технологии",
    "спорт",
    "кино",
    "бизнес",
    "образование",
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
    month = datetime.now().month
    # Boost seasonally-relevant niches
    seasonal_map = {
        (12, 1, 2): ["здоровье", "финансы", "технологии", "кино"],
        (3, 4, 5): ["технологии", "путешествия", "образование", "авто"],
        (6, 7, 8): ["путешествия", "спорт", "авто", "технологии"],
        (9, 10, 11): ["образование", "бизнес", "здоровье", "искусственный интеллект"],
    }
    for months, niches in seasonal_map.items():
        if month in months:
            seasonal_pool = niches
            break
    else:
        seasonal_pool = FALLBACK_NICHES

    # Weighted pick: prefer niches that haven't been used recently
    idx = _read_rotation_index()
    niche = seasonal_pool[idx % len(seasonal_pool)]
    _save_rotation_index((idx + 1) % len(seasonal_pool))
    logger.info(f"Fallback rotation (seasonal): {niche}")
    return niche


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
    """Pick best niche from post engagement history (0 API calls)."""
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
        score = record.get("score") or 0
        niche_scores.setdefault(niche, []).append(score)

    if not niche_scores:
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
        return niche

    # 2. Post history analysis (0 API calls)
    niche = await _from_post_history()
    if niche:
        return niche

    try:
        system_prompt, user_template = _load_trend_prompt()
        today = datetime.now().strftime("%Y-%m-%d")
        user_prompt = (
            user_template.replace("{{base_niche}}", base_niche or "не указана")
            .replace("{{date}}", today)
        )
        result = await client.call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.9,
            max_tokens=100,
        )
        niche = result.strip().lower().rstrip(".!")
        if niche and len(niche) > 2:
            logger.info(f"DeepSeek niche: {niche}")
            return niche
    except Exception as e:
        logger.warning(f"DeepSeek trend analysis failed: {e}")

    return _rotate_fallback()


def _load_trend_prompt() -> tuple[str, str]:
    prompt_path = Path("prompts") / "trend_analysis.prompter"
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
