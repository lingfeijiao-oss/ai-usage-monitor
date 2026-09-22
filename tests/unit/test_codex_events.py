import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.event_normalizer import (
    normalize_rate_limit_event,
    normalize_thread_token_event,
)


class CodexEventTests(unittest.TestCase):
    def test_thread_token_event_is_privacy_filtered(self):
        raw = {
            "threadId": "thread-secret-id",
            "turnId": "turn-secret-id",
            "tokenUsage": {
                "modelContextWindow": 872000,
                "last": {
                    "inputTokens": 100,
                    "cachedInputTokens": 80,
                    "outputTokens": 20,
                    "reasoningOutputTokens": 5,
                    "totalTokens": 125,
                },
                "total": {
                    "inputTokens": 1000,
                    "cachedInputTokens": 800,
                    "outputTokens": 200,
                    "reasoningOutputTokens": 50,
                    "totalTokens": 1250,
                },
            },
        }
        result = normalize_thread_token_event(raw)
        self.assertEqual(result["scope"], "LOCAL_APP_SERVER_THREAD")
        self.assertEqual(result["last"]["totalTokens"], 125)
        self.assertNotIn("threadId", result)
        self.assertNotIn("turnId", result)

    def test_rate_limit_event_is_trigger_only(self):
        raw = {
            "rateLimits": {
                "limitId": "codex",
                "primary": {"usedPercent": 42},
                "rateLimitReachedType": None,
            }
        }
        result = normalize_rate_limit_event(raw)
        self.assertEqual(result["limitId"], "codex")
        self.assertTrue(result["hasPrimary"])
        self.assertNotIn("primary", result)


if __name__ == "__main__":
    unittest.main()
