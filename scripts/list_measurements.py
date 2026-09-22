from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "measurements"


def main():
    files = sorted(DATA.glob("*.json"))
    if not files:
        print("No measurements.")
        return 0

    print("STATE   MODEL              EFFORT   TOKENS        ELAPSED   SESSION")
    print("-" * 82)
    for path in files:
        item = json.loads(path.read_text(encoding="utf-8"))
        state = item.get("state", "?")
        selection = item.get("selection") or {}
        result = item.get("result") or {}
        model = str(selection.get("model") or "?")
        effort = str(selection.get("reasoningEffort") or "?")
        tokens = result.get("tokenDelta")
        elapsed = result.get("elapsedSeconds")
        token_text = "-" if tokens is None else f"{tokens:,}"
        elapsed_text = "-" if elapsed is None else f"{elapsed:.0f}s"
        print(
            f"{state:<7} {model:<18} {effort:<8} "
            f"{token_text:<13} {elapsed_text:<9} {item.get('sessionId')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
