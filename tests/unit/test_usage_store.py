import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from storage import UsageStore


class UsageStoreTests(unittest.TestCase):
    def test_records_aggregate_snapshot(self):
        snapshot = {
            "observedAt": "2026-09-22T10:00:00+00:00",
            "provider": "openai_codex",
            "quota": {
                "provenance": "VERIFIED",
                "ordinaryUsageAllowed": True,
                "buckets": [
                    {
                        "limitId": "codex",
                        "limitName": None,
                        "planType": "pro",
                        "primary": {
                            "usedPercent": 25,
                            "remainingPercent": 75.0,
                            "windowDurationMins": 300,
                            "resetsAt": 1800000000,
                        },
                        "secondary": None,
                        "rateLimitReachedType": None,
                    }
                ],
            },
            "tokenUsage": {
                "provenance": "VERIFIED",
                "summary": {
                    "lifetimeTokens": 1000,
                    "peakDailyTokens": 100,
                    "longestRunningTurnSec": 50,
                    "currentStreakDays": 2,
                    "longestStreakDays": 3,
                },
                "dailyUsageBuckets": [
                    {"startDate": "2026-09-22", "tokens": 100}
                ],
            },
        }

        with tempfile.TemporaryDirectory() as td:
            with UsageStore(Path(td) / "test.sqlite3") as store:
                store.record_snapshot(snapshot)
                q = store.latest_quota("openai_codex")
                t = store.latest_token_summary("openai_codex")
                self.assertEqual(q[0]["remainingPercent"], 75.0)
                self.assertEqual(t["lifetimeTokens"], 1000)
                self.assertEqual(store.count_samples(), {"quota": 1, "token": 1, "thread": 0})


if __name__ == "__main__":
    unittest.main()

