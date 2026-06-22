"""
import_vk_xls.py — импорт VK-статистики из XLS-экспорта.

Кидаете XLS-файл *community_common_*.xls* в корень Farm, запускаете скрипт,
он парсит, сохраняет дневные метрики и удаляет XLS.

Данные сохраняются в data/vk_daily_metrics.json (агрегированные по дням).
В post_history.json не пишет — дневные агрегаты не соответствуют отдельным постам.
"""
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DAILY_METRICS_PATH = Path("data") / "vk_daily_metrics.json"

try:
    import pandas as pd
except ImportError:
    logger.error("pandas not installed. Run: pip install pandas xlrd")
    sys.exit(1)


def find_xls():
    files = sorted(Path(".").glob("*community_common_*.xls*"))
    return [f for f in files if 10000 < f.stat().st_size < 50_000_000]


def parse_common_xls(path: Path) -> dict[str, dict]:
    df = pd.read_excel(path)
    daily = defaultdict(lambda: {
        "views": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "subscribers": 0
    })

    for _, row in df.iterrows():
        try:
            data_type = str(row.iloc[4]).strip()
            param = str(row.iloc[7]).strip()
            raw = row.iloc[8]
            value = int(raw) if pd.notna(raw) and str(raw).strip().isdigit() else 0
            date_raw = str(row.iloc[2]).strip()
        except (IndexError, ValueError):
            continue

        d = daily[date_raw]
        if "Просмотры" in data_type and "Посты" in param:
            d["views"] += value
        elif "Охват" in data_type and "Посты" in param:
            d["reach"] += value
        elif "Лайки" in data_type and "Посты" in param:
            d["likes"] += value
        elif "Комментарии" in data_type and "Посты" in param:
            d["comments"] += value
        elif "Поделились" in data_type and "Посты" in param:
            d["shares"] += value
        elif "Количество подписчиков" in data_type:
            d["subscribers"] = value

    return dict(daily)


def merge_metrics(existing: dict, new: dict) -> dict:
    merged = existing.copy()
    for date, metrics in new.items():
        if date in merged:
            for k, v in metrics.items():
                if v > 0:
                    merged[date][k] = v
        else:
            merged[date] = metrics
    return merged


def print_summary(metrics: dict):
    totals = {"views": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0}
    for m in metrics.values():
        for k in totals:
            totals[k] += m.get(k, 0)
    logger.info(f"Days: {len(metrics)}, Views: {totals['views']}, "
                f"Reach: {totals['reach']}, Likes: {totals['likes']}, "
                f"Comments: {totals['comments']}, Shares: {totals['shares']}")


def main():
    files = find_xls()
    if not files:
        logger.info("No XLS files found")
        return

    existing = {}
    if DAILY_METRICS_PATH.exists():
        existing = json.loads(DAILY_METRICS_PATH.read_text(encoding="utf-8"))

    combined = {}
    for f in files:
        try:
            daily = parse_common_xls(f)
            if daily:
                combined = merge_metrics(combined, daily)
                logger.info(f"Parsed {f.name}: {len(daily)} days")
            f.unlink()
        except Exception as e:
            logger.error(f"Failed {f.name}: {e}")

    if not combined:
        return

    merged = merge_metrics(existing, combined)
    DAILY_METRICS_PATH.write_text(
        json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"Saved {len(merged)} days to {DAILY_METRICS_PATH}")
    print_summary(merged)


if __name__ == "__main__":
    main()
