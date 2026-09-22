import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from managed.codex_managed import (
    ManagedRunError,
    ManagedRunSpec,
    build_dry_run_plan,
    quota_allows_managed_run,
)


CATALOG = {
    "provenance": "VERIFIED",
    "models": [
        {
            "model": "gpt-test",
            "id": "gpt-test",
            "displayName": "GPT Test",
            "supportedReasoningEfforts": [
                {"reasoningEffort": "high"},
                {"reasoningEffort": "ultra"},
            ],
        }
    ],
}


class ManagedRunTests(unittest.TestCase):
    def test_dry_run_excludes_prompt(self):
        spec = ManagedRunSpec(
            model="gpt-test",
            reasoning_effort="high",
            prompt="secret prompt body",
            cwd=r"D:\workspace",
        )
        plan = build_dry_run_plan(CATALOG, spec)
        self.assertEqual(plan["mode"], "MANAGED_THREAD")
        self.assertFalse(plan["executionRequested"])
        self.assertNotIn("prompt", plan["spec"])
        self.assertEqual(
            plan["spec"]["promptCharacterCount"],
            len("secret prompt body"),
        )

    def test_unsupported_effort_is_blocked(self):
        spec = ManagedRunSpec(
            model="gpt-test",
            reasoning_effort="max",
            prompt="x",
            cwd=r"D:\workspace",
        )
        with self.assertRaises(Exception):
            build_dry_run_plan(CATALOG, spec)

    def test_danger_full_access_is_blocked(self):
        spec = ManagedRunSpec(
            model="gpt-test",
            reasoning_effort="high",
            prompt="x",
            cwd=r"D:\workspace",
            sandbox="danger-full-access",
        )
        with self.assertRaises(ManagedRunError):
            build_dry_run_plan(CATALOG, spec)

    def test_quota_guard_blocks_zero_remaining(self):
        snapshot = {
            "quota": {
                "ordinaryUsageAllowed": False,
                "buckets": [
                    {
                        "limitId": "codex",
                        "primary": {"remainingPercent": 0.0},
                    }
                ],
            }
        }
        allowed, reason = quota_allows_managed_run(snapshot)
        self.assertFalse(allowed)
        self.assertTrue(reason)

    def test_quota_guard_allows_positive_remaining(self):
        snapshot = {
            "quota": {
                "ordinaryUsageAllowed": True,
                "buckets": [
                    {
                        "limitId": "codex",
                        "primary": {"remainingPercent": 50.0},
                    }
                ],
            }
        }
        allowed, _ = quota_allows_managed_run(snapshot)
        self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
