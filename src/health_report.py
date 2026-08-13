"""Build a local, dependency-free health summary for the content farm."""

from datetime import datetime, timezone
from pathlib import Path

from src.state_store import atomic_write_json, read_json

DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / "health_report.json"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def build_health_report(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    history = read_json(DATA_DIR / "post_history.json", [], critical=True)
    pending = read_json(DATA_DIR / "pending_vk.json", [], critical=True)
    run_result = read_json(DATA_DIR / "run_result.json", {})
    patterns = read_json(DATA_DIR / "learned_patterns.json", {})

    metric_dates = []
    measured_posts = 0
    for record in history if isinstance(history, list) else []:
        vk = (record.get("platforms") or {}).get("vk") or {}
        collected = _parse_datetime(vk.get("metrics_collected_at"))
        if collected:
            metric_dates.append(collected)
        if vk.get("views") is not None:
            measured_posts += 1

    latest_metric = max(metric_dates) if metric_dates else None
    metric_age_hours = (
        round((now - latest_metric).total_seconds() / 3600, 1)
        if latest_metric else None
    )
    warnings = []
    if pending:
        warnings.append(f"VK pending queue contains {len(pending)} post(s)")
    if metric_age_hours is None:
        warnings.append("VK metrics have never been collected")
    elif metric_age_hours > 72:
        warnings.append(f"VK metrics are stale ({metric_age_hours} hours)")
    if patterns.get("status") == "paused_until_sufficient_ai_metrics":
        warnings.append("Content learning is paused until enough AI metrics are collected")

    report = {
        "generated_at": now.isoformat(),
        "status": "warning" if warnings else "healthy",
        "last_run": run_result,
        "vk": {
            "pending_posts": len(pending) if isinstance(pending, list) else None,
            "measured_posts": measured_posts,
            "latest_metrics_at": latest_metric.isoformat() if latest_metric else None,
            "metrics_age_hours": metric_age_hours,
        },
        "telegram": {
            "delivery_tracking": "message_id_only",
            "views_available": False,
        },
        "learning": {
            "status": patterns.get("status", "active"),
            "minimum_measured_posts": patterns.get("minimum_measured_posts", 20),
        },
        "legacy_postmypost": {
            "enabled": False,
            "reason": "Archived; direct platform metrics are the source of truth",
        },
        "warnings": warnings,
    }
    return report


def main() -> None:
    report = build_health_report()
    atomic_write_json(OUTPUT_PATH, report)
    print(f"Farm health: {report['status']}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
