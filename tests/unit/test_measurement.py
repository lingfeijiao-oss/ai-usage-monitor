import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from analytics.measurement import (
    MeasurementError,
    build_measurement_result,
    validate_model_effort,
)


CATALOG = {
    "provenance": "VERIFIED",
    "models": [
        {
            "model": "gpt-test",
            "id": "gpt-test",
            "displayName": "GPT Test",
            "supportedReasoningEfforts": [
                {"reasoningEffort": "medium"},
                {"reasoningEffort": "high"},
            ],
        }
    ],
}


def snap(at, tokens, used, reset=2000):
    return {
        "observedAt": at,
        "quota": {
            "buckets": [
                {
                    "limitId": "codex",
                    "primary": {
                        "usedPercent": used,
                        "windowDurationMins": 10080,
                        "resetsAt": reset,
                    },
                }
            ]
        },
        "tokenUsage": {"summary": {"lifetimeTokens": tokens}},
    }


class MeasurementTests(unittest.TestCase):
    def test_catalog_validation(self):
        result = validate_model_effort(CATALOG, "gpt-test", "high")
        self.assertEqual(result["reasoningEffort"], "high")
        with self.assertRaises(MeasurementError):
            validate_model_effort(CATALOG, "gpt-test", "ultra")

    def test_delta_and_ratio(self):
        result = build_measurement_result(
            snap("2026-09-22T10:00:00+00:00", 1000, 20),
            snap("2026-09-22T10:10:00+00:00", 6000, 22),
            model="gpt-test",
            reasoning_effort="high",
        )
        self.assertEqual(result["tokenDelta"], 5000)
        self.assertEqual(result["quotaDeltas"][0]["usedPercentDelta"], 2.0)
        self.assertEqual(
            result["derivedRatios"][0]["tokensPerObservedQuotaPercent"],
            2500.0,
        )
        self.assertEqual(result["attributionProvenance"], "OBSERVED")

    def test_quota_reset_breaks_comparison(self):
        result = build_measurement_result(
            snap("2026-09-22T10:00:00+00:00", 1000, 99, reset=2000),
            snap("2026-09-22T11:00:00+00:00", 2000, 2, reset=3000),
            model="gpt-test",
            reasoning_effort="medium",
        )
        self.assertFalse(result["quotaDeltas"][0]["comparable"])
        self.assertIsNone(result["quotaDeltas"][0]["usedPercentDelta"])
        self.assertEqual(result["derivedRatios"], [])


if __name__ == "__main__":
    unittest.main()
