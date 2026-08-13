import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src import health_report
from src.state_store import atomic_write_json


class HealthReportTests(unittest.TestCase):
    def test_reports_pending_queue_and_stale_metrics(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            atomic_write_json(data_dir / "pending_vk.json", [{"publication_id": "1"}])
            atomic_write_json(data_dir / "post_history.json", [{
                "platforms": {"vk": {
                    "views": 10,
                    "metrics_collected_at": (now - timedelta(days=4)).isoformat(),
                }}
            }])
            atomic_write_json(data_dir / "learned_patterns.json", {
                "status": "paused_until_sufficient_ai_metrics",
                "minimum_measured_posts": 20,
            })
            with patch.object(health_report, "DATA_DIR", data_dir):
                report = health_report.build_health_report(now)

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["vk"]["pending_posts"], 1)
        self.assertEqual(report["vk"]["metrics_age_hours"], 96.0)
        self.assertFalse(report["legacy_postmypost"]["enabled"])


if __name__ == "__main__":
    unittest.main()
