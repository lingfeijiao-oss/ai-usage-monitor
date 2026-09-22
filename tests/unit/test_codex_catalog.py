import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.catalog import CODEX_CAPABILITIES, _normalize_model


class CodexCatalogTests(unittest.TestCase):
    def test_normalize_model_and_efforts(self):
        raw = {
            "id": "model-1",
            "model": "gpt-test",
            "displayName": "GPT Test",
            "description": "test",
            "isDefault": True,
            "hidden": False,
            "defaultReasoningEffort": "high",
            "supportedReasoningEfforts": [
                {"reasoningEffort": "medium", "description": "Medium"},
                {"reasoningEffort": "high", "description": "High"},
            ],
            "serviceTiers": [
                {"id": "default", "name": "Default", "description": "Default tier"}
            ],
        }
        result = _normalize_model(raw)
        self.assertEqual(result["model"], "gpt-test")
        self.assertEqual(
            [x["reasoningEffort"] for x in result["supportedReasoningEfforts"]],
            ["medium", "high"],
        )
        self.assertEqual(result["defaultReasoningEffort"], "high")

    def test_attribution_boundary(self):
        self.assertFalse(CODEX_CAPABILITIES.passive_model_attribution)
        self.assertTrue(CODEX_CAPABILITIES.managed_thread_attribution)


if __name__ == "__main__":
    unittest.main()
