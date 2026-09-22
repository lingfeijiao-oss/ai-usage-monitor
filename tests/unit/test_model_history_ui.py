import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ui.model_history_panel import (
    build_model_usage_view,
    effort_detail_lines,
    effort_summary_text,
    model_summary_text,
    percent_of,
)


class ModelHistoryUiTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "model": "gpt-6-astra",
                "reasoningEffort": "xhigh",
                "usage": {
                    "totalTokens": 1000,
                    "inputTokens": 900,
                    "cachedInputTokens": 720,
                    "newInputTokens": 180,
                },
            },
            {
                "model": "gpt-6-astra",
                "reasoningEffort": "medium",
                "usage": {
                    "totalTokens": 300,
                    "inputTokens": 250,
                    "cachedInputTokens": 100,
                    "newInputTokens": 150,
                },
            },
            {
                "model": "gpt-5.6-sol",
                "reasoningEffort": "high",
                "usage": {
                    "totalTokens": 500,
                    "inputTokens": 400,
                    "cachedInputTokens": 300,
                    "newInputTokens": 100,
                },
            },
        ]

    def test_model_effort_hierarchy_and_current(self):
        view = build_model_usage_view(
            self.rows,
            1800,
            current_model="gpt-6-astra",
            current_effort="xhigh",
        )
        self.assertEqual(view[0]["model"], "gpt-6-astra")
        self.assertEqual(f"{view[0]['projectSharePercent']:.2f}", "72.22")
        self.assertTrue(view[0]["isCurrent"])
        xhigh = view[0]["efforts"][0]
        self.assertTrue(xhigh["isCurrent"])
        self.assertEqual(f"{xhigh['modelSharePercent']:.2f}", "76.92")
        self.assertEqual(f"{xhigh['projectSharePercent']:.2f}", "55.56")

    def test_compact_text_values_fit_without_bar_suffix_dependency(self):
        view = build_model_usage_view(self.rows, 1800)
        model = view[0]
        effort = model["efforts"][0]

        self.assertEqual(
            model_summary_text(model),
            "1.3K · Project 72.22%",
        )
        self.assertEqual(
            effort_summary_text(effort),
            "1.0K · Model 76.92%",
        )

        project_line, cache_line = effort_detail_lines(effort)
        self.assertEqual(project_line, "Project 55.56%")
        self.assertIn("Cached 720 · 80.00%", cache_line)
        self.assertIn("New 180 · 20.00%", cache_line)

    def test_percent_of_zero_is_safe(self):
        self.assertEqual(percent_of(100, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
