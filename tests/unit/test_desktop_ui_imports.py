import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import ui.desktop_app as desktop_app
from ui.model_history_panel import ModelHistoryPanel


class DesktopUiImportTests(unittest.TestCase):
    def test_model_history_panel_is_bound_in_desktop_module(self):
        self.assertIs(
            desktop_app.ModelHistoryPanel,
            ModelHistoryPanel,
        )

    def test_desktop_app_class_exists(self):
        self.assertTrue(
            hasattr(desktop_app, "DesktopApp")
        )


if __name__ == "__main__":
    unittest.main()
