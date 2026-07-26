"""Import a browser-exported VK post metrics snapshot into post_history.json."""

import argparse
import json
from datetime import datetime
from pathlib import Path


DEFAULT_METRICS = Path("data/vk_browser_metrics.json")
DEFAULT_HISTORY = Path("data/post_history.json")


def import_metrics(metrics_path: Path, history_path: Path) -> tuple[int, int]:
    snapshot = json.loads(metrics_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    by_ref = {
        f"{item['owner_id']}_{item['post_id']}": item
        for item in snapshot.get("posts", [])
    }

    matched = 0
    changed = 0
    for record in history:
        vk = record.get("platforms", {}).get("vk") or {}
        if vk.get("post_id") is None:
            continue
        ref = f"{vk.get('owner_id')}_{vk['post_id']}"
        metric = by_ref.get(ref)
        if metric is None:
            continue
        matched += 1

        values = {
            "reach": metric["reach"],
            "views": metric["views"],
            "likes": metric["likes"],
            "comments": metric["comments"],
            "reposts": metric["reposts"],
            "bookmarks": metric["bookmarks"],
        }
        previous = {key: vk.get(key) for key in values}
        vk.update(values)
        vk["metrics_collected_at"] = snapshot["collected_at"]
        vk.setdefault("metric_snapshots", {})["latest"] = {
            **values,
            "collected_at": snapshot["collected_at"],
            "source": "vk_browser",
        }
        if previous != values:
            changed += 1

    if matched:
        history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return matched, changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()

    matched, changed = import_metrics(args.metrics, args.history)
    print(
        f"Browser metrics imported at {datetime.now().isoformat()}: "
        f"matched={matched}, changed={changed}"
    )


if __name__ == "__main__":
    main()
