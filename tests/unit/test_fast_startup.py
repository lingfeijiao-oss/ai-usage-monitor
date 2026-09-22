import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import ui.desktop_app as app


class FastStartupTests(unittest.TestCase):
    def test_prioritizes_cached_auth_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first"
            cached = root / "cached"
            first.mkdir()
            cached.mkdir()

            state = root / "startup.json"
            state.write_text(
                json.dumps(
                    {
                        "authProfile": str(cached),
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                app,
                "STARTUP_STATE",
                state,
            ):
                ordered = (
                    app.prioritize_auth_profiles(
                        [first, cached]
                    )
                )

            self.assertEqual(
                ordered[0],
                cached,
            )

    def test_cached_project_report_loads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cache = root / "project.json"
            cache.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "projectName": "A",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                app,
                "PROJECT_CACHE",
                cache,
            ), patch.object(
                app,
                "LEGACY_PROJECT_CACHE",
                root / "missing.json",
            ):
                report = (
                    app.load_cached_project_report()
                )

            self.assertEqual(
                report["projects"][0][
                    "projectName"
                ],
                "A",
            )


if __name__ == "__main__":
    unittest.main()
