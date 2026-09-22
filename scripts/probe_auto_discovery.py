from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.codex_discovery import discovery_report, save_local_discovery


def main() -> int:
    print("=== Automatic Codex Discovery ===")
    print("No user-selected drive or path is required.")
    print("")

    report = discovery_report()
    installs = report["installs"]
    profiles = report["profiles"]
    selected = report["selectedInstall"]

    print(f"Validated Codex installations: {len(installs)}")
    for item in installs:
        print(
            f"  {item['version']} "
            f"app-server={item['app_server']} "
            f"source={item['discovery_source']}"
        )
        print(f"    {item['executable']}")

    print("")
    print(f"Detected Codex profiles: {len(profiles)}")
    for item in profiles:
        print(
            f"  {item['path']} "
            f"[{item['discovery_source']}]"
        )

    print("")
    if selected:
        print("Selected runtime:")
        print(f"  {selected['executable']}")
        print(f"  {selected['version']}")
    else:
        print("Selected runtime: NONE")
        print(
            "The final desktop application will offer the official Codex "
            "installation flow automatically when this occurs."
        )

    path = save_local_discovery(ROOT, report)
    print("")
    print(f"Local discovery cache: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
