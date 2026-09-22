import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.provider import normalize_rate_limits, normalize_usage


class CodexProviderNormalizationTests(unittest.TestCase):
    def test_rate_limit_remaining_and_multibucket(self):
        raw = {
            "ordinaryUsageAllowed": True,
            "rateLimitsByLimitId": {
                "codex": {
                    "limitId": "codex",
                    "primary": {
                        "usedPercent": 31,
                        "windowDurationMins": 300,
                        "resetsAt": 1800000000,
                    },
                },
                "base_model_inference": {
                    "limitId": "base_model_inference",
                    "limitName": "reserve",
                    "primary": {
                        "usedPercent": 6,
                        "windowDurationMins": 10080,
                        "resetsAt": 1800000100,
                    },
                },
            },
        }
        normalized = normalize_rate_limits(raw)
        self.assertEqual(normalized["provenance"], "VERIFIED")
        self.assertEqual(len(normalized["buckets"]), 2)
        codex = next(x for x in normalized["buckets"] if x["limitId"] == "codex")
        self.assertEqual(codex["primary"]["remainingPercent"], 69.0)

    def test_usage_filters_to_metrics(self):
        raw = {
            "summary": {
                "lifetimeTokens": 123,
                "peakDailyTokens": 45,
                "unexpected": "not copied",
            },
            "dailyUsageBuckets": [
                {"startDate": "2026-09-21", "tokens": 12, "private": "ignored"}
            ],
        }
        normalized = normalize_usage(raw)
        self.assertEqual(normalized["summary"]["lifetimeTokens"], 123)
        self.assertNotIn("unexpected", normalized["summary"])
        self.assertEqual(
            normalized["dailyUsageBuckets"],
            [{"startDate": "2026-09-21", "tokens": 12}],
        )


if __name__ == "__main__":
    unittest.main()
