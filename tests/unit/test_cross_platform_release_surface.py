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

            if "D:\\\\" in text or "D:\\" in text:
                offenders.append(
                    str(path.relative_to(ROOT))
                )

        self.assertEqual(
            offenders,
            [],
        )

    def test_native_build_matrix_is_present(self):
        workflow = (
            ROOT
            / ".github"
            / "workflows"
            / "build-desktop.yml"
        ).read_text(
            encoding="utf-8-sig"
        )

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
            self.assertIn(
                expected,
                workflow,
            )

    def test_packaged_smoke_gates_are_present(self):
        workflow = (
            ROOT
            / ".github"
            / "workflows"
            / "build-desktop.yml"
        ).read_text(
            encoding="utf-8-sig"
        )

        for expected in (
            "Smoke packaged Windows executable",
            "Smoke packaged macOS ARM64 app",
            "Smoke packaged macOS Intel app",
            "Smoke packaged Linux executable",
            "AIUsageMonitor.exe",
            "AIUsageMonitor.app/Contents/MacOS/AIUsageMonitor --smoke",
            "./dist/ai-usage-monitor --smoke",
        ):
            self.assertIn(
                expected,
                workflow,
            )

    def test_sha256_manifests_are_present(self):
        workflow = (
            ROOT
            / ".github"
            / "workflows"
            / "build-desktop.yml"
        ).read_text(
            encoding="utf-8-sig"
        )

        for expected in (
            "SHA256SUMS-windows-x64.txt",
            "SHA256SUMS-macOS-arm64.txt",
            "SHA256SUMS-macOS-x64.txt",
            "SHA256SUMS-linux-amd64.txt",
        ):
            self.assertIn(
                expected,
                workflow,
            )


    def test_prerelease_automation_is_present(self):
        workflow = (
            ROOT
            / ".github"
            / "workflows"
            / "build-desktop.yml"
        ).read_text(
            encoding="utf-8-sig"
        )

        for expected in (
            "release-prerelease:",
            "actions/download-artifact@v8",
            "contents: write",
            "gh release create",
            "--verify-tag",
            "--prerelease",
            "--latest=false",
            "release-notes.md",
        ):
            self.assertIn(
                expected,
                workflow,
            )


if __name__ == "__main__":
    unittest.main()

