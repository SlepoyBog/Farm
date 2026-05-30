import json
import logging
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.deepseek_client import DeepSeekClient
from src.trend_reader import fetch_recent_headlines

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
LAST_NICHES_FILE = Path("data") / "last_niches.json"


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


def _load_last_niches() -> list[str]:
    if LAST_NICHES_FILE.exists():
        try:
            return json.loads(LAST_NICHES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_last_niches(niches: list[str]):
    LAST_NICHES_FILE.write_text(json.dumps(niches), encoding="utf-8")

def _ensure_diversity(candidate: str, last_niches: list[str]) -> str:
    if not last_niches:
        return candidate
    if len(last_niches) >= 3 and len(set(last_niches)) == 1:
        logger.info(f"Forced rotation: same niche {last_niches[0]} for 3+ runs")
        idx = PREDEFINED_NICHES.index(last_niches[0])
        return PREDEFINED_NICHES[(idx + 1) % len(PREDEFINED_NICHES)]
    if candidate == last_niches[-1]:
        idx = PREDEFINED_NICHES.index(candidate)
        next_niche = PREDEFINED_NICHES[(idx + 1) % len(PREDEFINED_NICHES)]
        logger.info(f"Diversity shift: {candidate} → {next_niche} (same as last)")
        return next_niche
    return candidate

def _append_niche(niche: str, last_niches: list[str]):
    last_niches.append(niche)
    if len(last_niches) > 5:
        last_niches.pop(0)
    _save_last_niches(last_niches)


async def detect_trending_niche(
    client: DeepSeekClient,
    base_niche: str = "",
) -> str:
    logger.info("Analyzing trending niches...")

    last_niches = _load_last_niches()

    # Strategy: 50% rotation (for diversity), 40% RSS+DeepSeek, 10% post history
    roll = random.random()

    if roll < 0.5:
        niche = _rotate_fallback()
        niche = _ensure_diversity(niche, last_niches)
        _append_niche(niche, last_niches)
        logger.info(f"Rotation pick: {niche} (roll={roll:.2f})")
        return niche

    if roll < 0.9:
        niche = await _from_rss_with_deepseek(client, base_niche)
        if niche:
            niche = _ensure_diversity(niche, last_niches)
            _append_niche(niche, last_niches)
            logger.info(f"RSS+DeepSeek pick: {niche} (roll={roll:.2f})")
            return niche

    niche = _rotate_fallback()
    _append_niche(niche, last_niches)
    logger.info(f"Fallback pick: {niche}")
    return niche


async def _from_rss_with_deepseek(client: DeepSeekClient, base_niche: str = "") -> str | None:
    """Fetch fresh RSS headlines and ask DeepSeek to pick the hottest niche."""
    headlines = fetch_recent_headlines(hours=6, max_total=50)
    if not headlines:
        logger.info("No RSS headlines fetched, skipping RSS+DeepSeek path")
        return None

    headlines_text = "\n".join(f"- {h}" for h in headlines[:30])
    predefined_list = "\n".join(f"- {n}" for n in PREDEFINED_NICHES)
    prompt = (
        f"Сегодня {datetime.now().strftime('%d %B %Y')}. "
        f"Вот свежие заголовки новостей (за последние часы):\n\n"
        f"{headlines_text}\n\n"
        f"Проанализируй их. Какая ниша из списка ниже сейчас САМАЯ ГОРЯЧАЯ "
        f"судя по этим заголовкам?\n\n"
        f"{predefined_list}\n\n"
        f"Верни ТОЛЬКО название ниши из списка, ровно одну строку. Ничего другого."
    )
    try:
        result = await client.call(
            prompt=prompt,
            system_prompt="Ты — аналитик трендов. Анализируй заголовки и выбирай нишу только из предложенного списка.",
            temperature=0.3,
            max_tokens=50,
        )
        mapped = _map_to_predefined_niche(result.strip())
        if mapped:
            logger.info(f"RSS+DeepSeek trend: '{mapped}'")
            return mapped
        logger.warning(f"RSS+DeepSeek returned unmappable niche: '{result.strip()}'")
    except Exception as e:
        logger.warning(f"RSS+DeepSeek analysis failed: {e}")
    return None



