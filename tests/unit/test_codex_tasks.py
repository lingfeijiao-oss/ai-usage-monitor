import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.tasks import (
    hash_identifier,
    normalize_thread,
    safe_task,
)


class CodexTaskTests(unittest.TestCase):
    def test_normalize_thread_privacy_boundary(self):
        raw = {
            "id": "thread-secret",
            "name": "Fix tests",
            "preview": "full prompt body",
            "cwd": r"D:\Aevora",
            "model": "gpt-6-astra",
            "reasoningEffort": "high",
            "createdAt": 100,
            "updatedAt": 200,
            "source": {"type": "cli"},
        }

        task = normalize_thread(
            raw,
            Path(r"D:\.codex"),
        )

        self.assertEqual(
            task["title"],
            "Fix tests",
        )
        self.assertEqual(
            task["projectName"],
            "Aevora",
        )
        self.assertEqual(
            task["sourceKind"],
            "cli",
        )
        self.assertEqual(
            task["_threadId"],
            "thread-secret",
        )

        persisted = safe_task(task)

        self.assertNotIn(
            "_threadId",
            persisted,
        )
        self.assertEqual(
            persisted["threadIdHash"],
            hash_identifier("thread-secret"),
        )
        self.assertNotIn(
            "cwd",
            persisted,
        )

    def test_preview_is_bounded(self):
        raw = {
            "id": "x",
            "preview": "a" * 500,
        }

        task = normalize_thread(
            raw,
            Path("."),
        )

        self.assertLessEqual(
            len(task["title"]),
            120,
        )


if __name__ == "__main__":
    unittest.main()
