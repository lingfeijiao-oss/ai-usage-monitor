import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


class CrossPlatformReleaseSurfaceTests(unittest.TestCase):
    def test_runtime_source_has_no_development_d_drive_literal(self):
        offenders = []
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if 'D:\\\\' in text or 'D:\\' in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_native_build_matrix_is_present(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-desktop.yml"
        ).read_text(encoding="utf-8-sig")

        for expected in (
            "runs-on: windows-latest",
            "runs-on: macos-latest",
            "runs-on: macos-15-intel",
            "runs-on: ubuntu-latest",
            "AIUsageMonitor-macOS-arm64.dmg",
            "AIUsageMonitor-macOS-x64.dmg",
            "AIUsageMonitor-Setup-Windows-x64.exe",
            "ai-usage-monitor_0.3.1_amd64.deb",
        ):
            self.assertIn(expected, workflow)


if __name__ == "__main__":
    unittest.main()
