import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from analytics.project_usage import aggregate_projects, scan_rollout


def write_rollout(path: Path):
    rows = [
        {
            "timestamp": "2026-09-22T01:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": "thread-1",
                "cwd": r"D:\Aevora",
            },
        },
        {
            "timestamp": "2026-09-22T01:00:01Z",
            "type": "turn_context",
            "payload": {
                "turn_id": "turn-1",
                "model": "gpt-6-astra",
                "effort": "xhigh",
            },
        },
        {
            "timestamp": "2026-09-22T01:00:10Z",
            "type": "token_usage_record",
            "payload": {
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "response_id": "response-1",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 800,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 100,
                    "reasoning_output_tokens": 40,
                    "total_tokens": 1100,
                },
            },
        },
        # Duplicate response must not double count.
        {
            "timestamp": "2026-09-22T01:00:11Z",
            "type": "token_usage_record",
            "payload": {
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "response_id": "response-1",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 800,
                    "output_tokens": 100,
                    "reasoning_output_tokens": 40,
                    "total_tokens": 1100,
                },
            },
        },
        {
            "timestamp": "2026-09-22T01:01:00Z",
            "type": "turn_context",
            "payload": {
                "turn_id": "turn-2",
                "model": "gpt-5.6-sol",
                "effort": "high",
            },
        },
        {
            "timestamp": "2026-09-22T01:01:10Z",
            "type": "token_usage_record",
            "payload": {
                "thread_id": "thread-1",
                "turn_id": "turn-2",
                "response_id": "response-2",
                "usage": {
                    "input_tokens": 500,
                    "cached_input_tokens": 100,
                    "cache_write_input_tokens": 10,
                    "output_tokens": 50,
                    "reasoning_output_tokens": 20,
                    "total_tokens": 550,
                },
            },
        },
        # Prompt-like content must be ignored entirely by the scanner.
        {
            "timestamp": "2026-09-22T01:01:11Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "PRIVATE PROMPT"}],
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


class ProjectUsageTests(unittest.TestCase):
    def test_project_folder_token_and_model_aggregation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rollout-test.jsonl"
            write_rollout(path)
            summary = scan_rollout(path)

            self.assertEqual(summary.project_path, r"D:\Aevora")
            self.assertEqual(summary.latest_model, "gpt-5.6-sol")
            self.assertEqual(summary.latest_effort, "high")
            self.assertEqual(len(summary.response_usage), 2)

            report = aggregate_projects([summary])
            self.assertEqual(len(report), 1)

            project = report[0]
            usage = project["usage"]

            self.assertEqual(usage["inputTokens"], 1500)
            self.assertEqual(usage["cachedInputTokens"], 900)
            self.assertEqual(usage["newInputTokens"], 600)
            self.assertEqual(usage["outputTokens"], 150)
            self.assertEqual(usage["reasoningOutputTokens"], 60)
            self.assertEqual(usage["totalTokens"], 1650)
            self.assertEqual(project["currentModel"], "gpt-5.6-sol")
            self.assertEqual(project["currentReasoningEffort"], "high")
            self.assertEqual(len(project["byModelAndEffort"]), 2)
            self.assertEqual(len(project["modelSwitches"]), 1)


if __name__ == "__main__":
    unittest.main()
