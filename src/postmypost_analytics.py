"""Collect VK analytics from Postmypost without a browser or user PC."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


logger = logging.getLogger(__name__)

API_URL = "https://api.postmypost.io/v4.1/analytics/publications"
DEFAULT_PROJECT_ID = "353549"
DEFAULT_ACCOUNT_ID = "2205063"
DEFAULT_OUTPUT = Path("data/postmypost_metrics.json")
DEFAULT_HISTORY = Path("data/post_history.json")


def _walk_values(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower(), child
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


def _find_value(data: dict, aliases: tuple[str, ...], default=None):
    wanted = {alias.lower() for alias in aliases}
    for key, value in _walk_values(data):
        if key in wanted and value not in (None, ""):
            return value
    return default


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
        try:
            return int(float(cleaned))
        except ValueError:
            return 0
    return 0


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("\xa0", "").replace(" ", "").replace("%", "")
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def normalize_publication(item: dict) -> dict:
    """Convert API response variants to Farm's stable metric schema."""
    url = str(
        _find_value(item, ("url", "link", "permalink", "publication_url"), "")
    )
    post_id = _find_value(
        item,
        ("post_id", "external_id", "social_id", "network_id", "remote_id"),
    )
    if post_id is None and url:
        match = re.search(r"wall-?\d+_(\d+)", url)
        if match:
            post_id = match.group(1)

    return {
        "post_id": _as_int(post_id) or None,
        "publication_id": _find_value(item, ("publication_id", "id")),
        "text": str(
            _find_value(item, ("text", "message", "caption", "description"), "")
        ).strip(),
        "published_at": str(
            _find_value(
                item,
                ("published_at", "publication_date", "published", "date", "created_at"),
                "",
            )
        ),
        "url": url,
        "actions": _as_int(_find_value(item, ("actions", "action_count"), 0)),
        "reactions": _as_int(
            _find_value(item, ("reactions", "reaction_count", "likes", "like_count"), 0)
        ),
        "comments": _as_int(
            _find_value(item, ("comments", "comment_count"), 0)
        ),
        "views": _as_int(_find_value(item, ("views", "view_count"), 0)),
        "reach": _as_int(_find_value(item, ("reach", "reach_count"), 0)),
        "err": _as_float(_find_value(item, ("err",), 0)),
        "erv": _as_float(_find_value(item, ("erv",), 0)),
    }


def fetch_publications(
    token: str,
    project_id: str,
    account_id: str,
    date_from: date,
    date_to: date,
    session=requests,
) -> list[dict]:
    """Fetch all available post analytics pages for a period."""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    publications: list[dict] = []

    for page in range(1, 101):
        response = session.get(
            API_URL,
            headers=headers,
            params={
                "project_id": project_id,
                "account_id": account_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "type": 1,
                "page": page,
                "per_page": 50,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("data", [])
        if not isinstance(batch, list):
            raise ValueError("Postmypost response field 'data' is not a list")

        publications.extend(normalize_publication(item) for item in batch)
        if len(batch) < 50:
            break

    return publications


def _text_key(value: str) -> str:
    return " ".join(re.findall(r"[a-zа-яё0-9]+", value.lower()))


def _matches_record(metric: dict, record: dict) -> bool:
    vk = record.get("platforms", {}).get("vk") or {}
    if metric.get("post_id") and vk.get("post_id"):
        return int(metric["post_id"]) == int(vk["post_id"])

    metric_text = _text_key(metric.get("text", ""))
    if not metric_text:
        return False
    for candidate in (record.get("title", ""), record.get("topic", "")):
        candidate_key = _text_key(candidate)
        if len(candidate_key) >= 15 and candidate_key in metric_text:
            return True
    return False


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _nearest_metric_by_time(
    publications: list[dict],
    record: dict,
) -> dict | None:
    """Match RSS publications when Postmypost omits their text."""
    record_time = _parse_datetime(record.get("published_at", ""))
    if record_time is None:
        return None

    candidates = []
    for metric in publications:
        metric_time = _parse_datetime(metric.get("published_at", ""))
        if metric_time is None:
            continue
        delay = (metric_time - record_time).total_seconds()
        if -5 * 60 <= delay <= 45 * 60:
            candidates.append((abs(delay), metric))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def import_into_history(
    publications: list[dict],
    history_path: Path = DEFAULT_HISTORY,
    collected_at: str | None = None,
) -> tuple[int, int]:
    if not history_path.exists():
        return 0, 0

    history = json.loads(history_path.read_text(encoding="utf-8"))
    timestamp = collected_at or datetime.now(timezone.utc).isoformat()
    matched = 0
    changed = 0
    available = list(publications)

    for record in history:
        metric = next(
            (item for item in available if _matches_record(item, record)),
            None,
        )
        saved_vk = record.get("platforms", {}).get("vk") or {}
        if metric is None and not saved_vk.get("post_id"):
            metric = _nearest_metric_by_time(available, record)
        if metric is None:
            continue
        available.remove(metric)

        matched += 1
        vk = record.setdefault("platforms", {}).setdefault("vk", {})
        values = {
            "views": metric["views"],
            "reach": metric["reach"],
            "likes": metric["reactions"],
            "comments": metric["comments"],
            "actions": metric["actions"],
            "err": metric["err"],
            "erv": metric["erv"],
        }
        previous = {key: vk.get(key) for key in values}
        vk.update(values)
        if metric.get("post_id"):
            vk["post_id"] = metric["post_id"]
        if metric.get("publication_id"):
            vk["publication_id"] = metric["publication_id"]
        if metric.get("url"):
            vk["url"] = metric["url"]
        if metric.get("published_at"):
            vk["published_at"] = metric["published_at"]
        vk["metrics_collected_at"] = timestamp
        vk.setdefault("metric_snapshots", {})["latest"] = {
            **values,
            "collected_at": timestamp,
            "source": "postmypost_api",
        }
        if previous != values:
            changed += 1

    if matched:
        history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return matched, changed


def collect_and_save(
    token: str,
    project_id: str = DEFAULT_PROJECT_ID,
    account_id: str = DEFAULT_ACCOUNT_ID,
    days: int = 30,
    output_path: Path = DEFAULT_OUTPUT,
    history_path: Path = DEFAULT_HISTORY,
) -> dict:
    today = date.today()
    publications = fetch_publications(
        token=token,
        project_id=project_id,
        account_id=account_id,
        date_from=today - timedelta(days=max(1, days)),
        date_to=today,
    )
    collected_at = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "source": "postmypost_api",
        "project_id": project_id,
        "account_id": account_id,
        "collected_at": collected_at,
        "posts": publications,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    matched, changed = import_into_history(
        publications,
        history_path=history_path,
        collected_at=collected_at,
    )
    return {
        "posts": len(publications),
        "matched": matched,
        "changed": changed,
        "output": str(output_path),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    token = os.getenv("POSTMYPOST_API_TOKEN", "").strip()
    if not token:
        logger.info("POSTMYPOST_API_TOKEN is not configured; skipping analytics.")
        return

    result = collect_and_save(
        token=token,
        project_id=os.getenv("POSTMYPOST_PROJECT_ID", DEFAULT_PROJECT_ID),
        account_id=os.getenv("POSTMYPOST_ACCOUNT_ID", DEFAULT_ACCOUNT_ID),
        days=int(os.getenv("POSTMYPOST_ANALYTICS_DAYS", "30")),
    )
    logger.info(
        "Postmypost analytics: posts=%s matched=%s changed=%s",
        result["posts"],
        result["matched"],
        result["changed"],
    )


if __name__ == "__main__":
    main()
