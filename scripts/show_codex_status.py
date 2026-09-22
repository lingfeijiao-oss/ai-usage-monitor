from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from storage import UsageStore  # noqa: E402


def reset_text(value):
    if not isinstance(value, int):
        return "unknown"
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def main():
    db = ROOT / "data" / "usage.sqlite3"
    if not db.is_file():
        print("No monitor database yet.")
        return 2

    with UsageStore(db) as store:
        counts = store.count_samples()
        print("=== Codex monitor status ===")
        print(f"Quota samples: {counts['quota']}")
        print(f"Token samples: {counts['token']}")
        print("")
        for row in store.latest_quota("openai_codex"):
            print(
                f"{row['limitId']}/{row['windowKind']}: "
                f"used={row['usedPercent']}% "
                f"remaining={row['remainingPercent']}% "
                f"reset={reset_text(row['resetsAt'])} "
                f"[{row['provenance']}]"
            )
        token = store.latest_token_summary("openai_codex")
        if token:
            print("")
            print(
                f"Lifetime tokens: {token['lifetimeTokens']:,} "
                f"[{token['provenance']}]"
            )
            print(f"Observed: {token['observedAt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
