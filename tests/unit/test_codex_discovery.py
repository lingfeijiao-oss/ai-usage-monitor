import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core.codex_discovery import (
    CodexInstall,
    choose_install,
    discover_profiles,
    install_rank,
)


class CodexDiscoveryTests(unittest.TestCase):
    def test_choose_app_server_install(self):
        installs = [
            CodexInstall(
                executable=r"C:\x\codex.exe",
                version="codex-cli 0.154.0",
                app_server=False,
                discovery_source="PATH",
            ),
            CodexInstall(
                executable=r"F:\tools\codex.exe",
                version="codex-cli 0.153.0",
                app_server=True,
                discovery_source="COMMON_LOCATION",
            ),
        ]
        chosen = choose_install(installs)
        self.assertEqual(chosen.executable, r"F:\tools\codex.exe")

    def test_stable_normal_runtime_beats_internal_alpha_helpers(self):
        installs = [
            CodexInstall(
                executable=r"C:\Users\u\.codex\.sandbox-bin\codex.exe",
                version="codex-cli 0.151.0-alpha.7.2",
                app_server=True,
                discovery_source="BOUNDED_LOCAL_SCAN",
            ),
            CodexInstall(
                executable=r"C:\Users\u\.codex\plugins\.plugin-appserver\codex.exe",
                version="codex-cli 0.155.0-alpha.9.2",
                app_server=True,
                discovery_source="BOUNDED_LOCAL_SCAN",
            ),
            CodexInstall(
                executable=r"F:\TestRuntime\Codex\bin\codex.exe",
                version="codex-cli 0.155.1",
                app_server=True,
                discovery_source="PATH",
            ),
        ]
        chosen = choose_install(installs)
        self.assertEqual(
            chosen.executable,
            r"F:\TestRuntime\Codex\bin\codex.exe",
        )

    def test_internal_helper_is_penalized_even_when_version_is_newer(self):
        helper = CodexInstall(
            executable=r"C:\Users\u\.codex\.sandbox-bin\codex.exe",
            version="codex-cli 0.999.0",
            app_server=True,
            discovery_source="BOUNDED_LOCAL_SCAN",
        )
        normal = CodexInstall(
            executable=r"F:\Codex\codex.exe",
            version="codex-cli 0.155.1",
            app_server=True,
            discovery_source="COMMON_LOCATION",
        )
        self.assertGreater(install_rank(normal), install_rank(helper))

    def test_profiles_are_automatic_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".codex"
            home.mkdir()

            with patch(
                "core.codex_discovery.Path.home",
                return_value=Path(td),
            ):
                with patch(
                    "core.codex_discovery.windows_fixed_drive_roots",
                    return_value=[],
                ):
                    profiles = discover_profiles([])

            self.assertEqual(len(profiles), 1)
            self.assertEqual(Path(profiles[0].path), home)


if __name__ == "__main__":
    unittest.main()


