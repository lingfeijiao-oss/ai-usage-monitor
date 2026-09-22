import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from analytics.project_watcher import ProjectUsageWatcher


def append(path, row):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


class ProjectWatcherTests(unittest.TestCase):
    def test_incremental_refresh_observes_changed_rollout(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td) / ".codex"
            sessions = profile / "sessions" / "2026" / "09" / "22"
            sessions.mkdir(parents=True)
            rollout = sessions / "rollout-test.jsonl"

            append(
                rollout,
                {
                    "timestamp": "2026-09-22T01:00:00Z",
                    "type": "session_meta",
                    "payload": {"cwd": r"D:\Aevora", "id": "t"},
                },
            )
            append(
                rollout,
                {
                    "timestamp": "2026-09-22T01:00:01Z",
                    "type": "turn_context",
                    "payload": {
                        "turn_id": "a",
                        "model": "gpt-6-astra",
                        "effort": "xhigh",
                    },
                },
            )

            watcher = ProjectUsageWatcher([profile])
            first = watcher.refresh()
            self.assertEqual(
                first["projects"][0]["currentModel"],
                "gpt-6-astra",
            )

            append(
                rollout,
                {
                    "timestamp": "2026-09-22T01:00:02Z",
                    "type": "turn_context",
                    "payload": {
                        "turn_id": "b",
                        "model": "gpt-5.6-sol",
                        "effort": "high",
                    },
                },
            )

            second = watcher.refresh()
            project = second["projects"][0]
            self.assertEqual(project["currentModel"], "gpt-5.6-sol")
            self.assertEqual(project["currentReasoningEffort"], "high")
            self.assertEqual(len(project["modelSwitches"]), 1)


if __name__ == "__main__":
    unittest.main()
