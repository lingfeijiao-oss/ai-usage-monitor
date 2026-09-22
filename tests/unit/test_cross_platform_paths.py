import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core import app_paths
from core.codex_discovery import fast_install_candidates
from analytics.project_usage import (
    _normalize_project_path,
    _project_identity_key,
    _project_name,
)


def portable_path_strings(rows):
    # On a Windows test host, Path("/usr/local/...") is represented internally
    # as a WindowsPath. as_posix() gives us a host-independent assertion form.
    return {
        path.as_posix()
        for path, _ in rows
    }


class CrossPlatformPathTests(unittest.TestCase):
    def test_windows_project_path(self):
        value = _normalize_project_path(r"D:\Aevora")
        self.assertEqual(value, r"D:\Aevora")
        self.assertEqual(_project_name(value), "Aevora")
        self.assertEqual(
            _project_identity_key(r"D:\Aevora"),
            _project_identity_key(r"d:\aevora"),
        )

    def test_posix_project_path_preserves_case(self):
        value = _normalize_project_path("/Users/test/Aevora")
        self.assertEqual(value, "/Users/test/Aevora")
        self.assertEqual(_project_name(value), "Aevora")
        self.assertNotEqual(
            _project_identity_key("/work/Aevora"),
            _project_identity_key("/work/aevora"),
        )

    def test_macos_candidates_include_homebrew(self):
        with patch(
            "core.codex_discovery._system",
            return_value="darwin",
        ):
            rows = fast_install_candidates()

        values = portable_path_strings(rows)

        self.assertIn(
            "/opt/homebrew/bin/codex",
            values,
        )
        self.assertIn(
            "/usr/local/bin/codex",
            values,
        )

    def test_linux_candidates_include_standard_paths(self):
        with patch(
            "core.codex_discovery._system",
            return_value="linux",
        ):
            rows = fast_install_candidates()

        values = portable_path_strings(rows)

        self.assertIn(
            "/usr/local/bin/codex",
            values,
        )
        self.assertIn(
            "/usr/bin/codex",
            values,
        )

    def test_linux_xdg_data_path(self):
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "core.app_paths.platform_id",
                return_value="linux",
            ):
                with patch.dict(
                    os.environ,
                    {"XDG_DATA_HOME": td},
                    clear=False,
                ):
                    self.assertTrue(
                        str(
                            app_paths.user_data_dir()
                        ).startswith(td)
                    )


if __name__ == "__main__":
    unittest.main()

