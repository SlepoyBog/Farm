"""
import_vk_xls.py — импорт VK-статистики из XLS-экспорта.

Кидаете XLS-файл *community_common_*.xls* в корень Farm, запускаете скрипт,
он парсит, сохраняет дневные метрики.

Данные сохраняются в data/vk_daily_metrics.json (агрегированные по дням).

Важно: XLS содержит как посты (per-post), так и дневные агрегаты.
Парсер берёт ТОЛЬКО дневные агрегаты — строки, где "Посты" и "Весь контент"
совпадают для одной метрики (это итоговая строка дня).
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


# Метрики, которые парсим: (type_contains, param1, param2)
# param1 = "Посты", param2 = "Весь контент"
# Берём значение ТОЛЬКО если `type`+`Посты` == `type`+`Весь контент` (это дневной агрегат)
METRICS = ["Просмотры", "Охват", "Лайки", "Комментарии", "Поделились"]


def find_xls():
    files = sorted(Path(".").glob("*community_common_*.xls*"))
    return [f for f in files if 10000 < f.stat().st_size < 50_000_000]


def dump_schema(path: Path):
    df = pd.read_excel(path)
    pairs = set()
    for _, row in df.iterrows():
        try:
            dt = str(row.iloc[4]).strip()
            param = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else ""
            pairs.add((dt, param))
        except (IndexError, ValueError):
            continue
    logger.info(f"=== UNIQUE (data_type, param) pairs in {path.name} ===")
    for dt, param in sorted(pairs):
        logger.info(f"  '{dt}' | '{param}'")


def parse_common_xls(path: Path) -> dict[str, dict]:
    df = pd.read_excel(path)
    daily = defaultdict(lambda: {
        "views": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "subscribers": 0
    })

    # Собираем все строки сгруппированно по (дата, тип_метрики, параметр)
    # Потом для каждой даты+типа проверяем: если "Посты" == "Весь контент" — это дневной агрегат
    raw_rows = defaultdict(lambda: {"Посты": {}, "Весь контент": {}})

    total_rows = 0
    for _, row in df.iterrows():
        total_rows += 1
        try:
            data_type = str(row.iloc[4]).strip()
            param = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else ""
            raw = row.iloc[8]
            value = int(raw) if pd.notna(raw) and str(raw).strip().isdigit() else 0
            date_raw = str(row.iloc[2]).strip()
        except (IndexError, ValueError):
            continue

        # Проверяем, что тип метрики нас интересует
        metric_key = None
        for m in METRICS:
            if m == data_type:
                metric_key = m
                break

        if metric_key is None:
            # Количество подписчиков
            if "Количество подписчиков" in data_type and value > 0:
                daily[date_raw]["subscribers"] = value
            continue

        if param in ("Посты", "Весь контент"):
            raw_rows[(date_raw, metric_key)][param] = value

    matched_days = 0
    for (date_raw, metric_key), params in raw_rows.items():
        posts_val = params.get("Посты", 0)
        all_val = params.get("Весь контент", 0)

        # Дневной агрегат: "Посты" и "Весь контент" одинаковы
        # Per-post: они разные (один из них 0 или не совпадают)
        if posts_val > 0 and posts_val == all_val:
            matched_days += 1
            d = daily[date_raw]
            if metric_key == "Просмотры":
                d["views"] = posts_val
            elif metric_key == "Охват":
                d["reach"] = posts_val
            elif metric_key == "Лайки":
                d["likes"] = posts_val
            elif metric_key == "Комментарии":
                d["comments"] = posts_val
            elif metric_key == "Поделились":
                d["shares"] = posts_val

    logger.info(f"Total rows: {total_rows}, Daily aggregates matched: {matched_days}")
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

    dump_schema(files[0])

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
        except Exception as e:
            logger.error(f"Failed {f.name}: {e}")

    if not combined:
        logger.info("No new data parsed")
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
