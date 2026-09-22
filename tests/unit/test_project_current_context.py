import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from analytics.project_usage import RolloutSummary, aggregate_projects


class ProjectCurrentContextTests(unittest.TestCase):
    def test_current_model_uses_latest_turn_context_not_latest_arbitrary_record(self):
        old_context_but_late_log = RolloutSummary(
            path=Path("a.jsonl"),
            project_path=r"D:\Aevora",
            project_name="Aevora",
            latest_epoch=300.0,
            latest_context_epoch=100.0,
            latest_model="gpt-6-astra",
            latest_effort="xhigh",
            turn_contexts={
                "a": (100.0, "gpt-6-astra", "xhigh"),
            },
        )

        newer_context = RolloutSummary(
            path=Path("b.jsonl"),
            project_path=r"D:\Aevora",
            project_name="Aevora",
            latest_epoch=250.0,
            latest_context_epoch=200.0,
            latest_model="gpt-5.6-sol",
            latest_effort="high",
            turn_contexts={
                "b": (200.0, "gpt-5.6-sol", "high"),
            },
        )

        project = aggregate_projects(
            [old_context_but_late_log, newer_context]
        )[0]

        self.assertEqual(project["currentModel"], "gpt-5.6-sol")
        self.assertEqual(project["currentReasoningEffort"], "high")
        self.assertEqual(len(project["modelSwitches"]), 1)
        self.assertEqual(
            project["modelSwitches"][0]["toModel"],
            "gpt-5.6-sol",
        )


if __name__ == "__main__":
    unittest.main()
