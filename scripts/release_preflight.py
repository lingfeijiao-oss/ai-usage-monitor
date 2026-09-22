from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

ERRORS: list[str] = []

REQUIRED = [
    ROOT / "LICENSE",
    ROOT / "README.md",
    ROOT / "PRIVACY.md",
    ROOT / "SECURITY.md",
    ROOT / "pyproject.toml",
    SRC / "main.py",
    SRC / "ui" / "desktop_app.py",
    SRC / "ui" / "model_history_panel.py",
]

FORBIDDEN_RELEASE_FILES = [
    SRC / "ui" / "dashboard_server.py",
    SRC / "ui" / "task_browser.py",
    ROOT / "scripts" / "run_dashboard.ps1",
    ROOT / "scripts" / "run_task_browser.ps1",
]

URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
DEV_DRIVE_PATTERN = re.compile(r'(?i)(?:r|u|f|rf|fr)?["\']D:\\\\')


def fail(message: str) -> None:
    ERRORS.append(message)


for path in REQUIRED:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")

for path in FORBIDDEN_RELEASE_FILES:
    if path.exists():
        fail(f"legacy release file still present: {path.relative_to(ROOT)}")

for path in SRC.rglob("*.py"):
    text = path.read_text(encoding="utf-8-sig")

    if URL_PATTERN.search(text):
        fail(f"literal HTTP/HTTPS URL in runtime source: {path.relative_to(ROOT)}")

    if DEV_DRIVE_PATTERN.search(text):
        fail(f"hard-coded D: development path in runtime source: {path.relative_to(ROOT)}")

for path in (ROOT / "scripts").glob("*.ps1"):
    text = path.read_text(encoding="utf-8-sig")

    if re.search(r"(?i)D:\\ai-usage-monitor", text):
        fail(f"hard-coded checkout path in public script: {path.relative_to(ROOT)}")

gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")

for required_ignore in (
    "data/",
    "schemas/",
    "config/local.*",
    "secrets/",
    "release/",
    "dist/",
    "build/",
):
    if required_ignore not in gitignore:
        fail(f".gitignore missing: {required_ignore}")

if ERRORS:
    print("Release preflight: BLOCKED")
    for error in ERRORS:
        print(f" - {error}")
    raise SystemExit(1)

print("Release preflight: PASS")
print("Runtime source has no literal external HTTP/HTTPS URL.")
print("Runtime source has no hard-coded D: development path.")
print("Legacy web/task-browser release entrypoints are absent.")
print("Local/generated state is excluded by .gitignore.")

