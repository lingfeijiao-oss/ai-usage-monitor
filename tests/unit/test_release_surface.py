import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


class ReleaseSurfaceTests(unittest.TestCase):
    def test_license_exists(self):
        self.assertTrue((ROOT / "LICENSE").is_file())

    def test_legacy_web_server_removed(self):
        self.assertFalse(
            (ROOT / "src" / "ui" / "dashboard_server.py").exists()
        )
        self.assertFalse(
            (ROOT / "scripts" / "run_dashboard.ps1").exists()
        )

    def test_legacy_task_browser_removed(self):
        self.assertFalse(
            (ROOT / "src" / "ui" / "task_browser.py").exists()
        )
        self.assertFalse(
            (ROOT / "scripts" / "run_task_browser.ps1").exists()
        )

    def test_gitignore_excludes_local_generated_state(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
        for expected in (
            "data/",
            "schemas/",
            "config/local.*",
            "secrets/",
            "release/",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
