from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from providers.openai_codex import CodexProvider  # noqa: E402


def local_reset_text(timestamp):
    if not isinstance(timestamp, (int, float)):
        return "unknown"
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def main() -> int:
    config_path = ROOT / "config" / "local.codex.json"
    if not config_path.is_file():
        print(f"ERROR: missing {config_path}")
        return 2

    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    provider = CodexProvider(
        Path(config["executable"]),
        Path(config["codex_home"]),
        codex_version=config.get("codex_version"),
    )
    snapshot = provider.read_snapshot()

    out_dir = ROOT / "data" / "codex"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "latest.json"
    latest.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("")
    print("=== OpenAI Codex Provider v0.1 ===")
    print(f"Provider: {snapshot['provider']}")
    print(f"Codex:    {snapshot.get('codexVersion') or 'unknown'}")
    print(f"Plan:     {snapshot['account'].get('planType') or 'unknown'}")
    print("")

    buckets = snapshot["quota"]["buckets"]
    if buckets:
        print("Quota (VERIFIED)")
        for bucket in buckets:
            name = bucket.get("limitName") or bucket.get("limitId") or "unnamed"
            print(f"  [{name}]")
            for label in ("primary", "secondary"):
                window = bucket.get(label)
                if not window:
                    continue
                used = window.get("usedPercent")
                remaining = window.get("remainingPercent")
                duration = window.get("windowDurationMins")
                reset = local_reset_text(window.get("resetsAt"))
                print(
                    f"    {label}: used={used}% remaining={remaining}% "
                    f"window={duration}min reset={reset}"
                )
    else:
        print("Quota: unavailable")

    print("")
    usage = snapshot["tokenUsage"]
    summary = usage.get("summary")
    if summary:
        print("Token usage (VERIFIED)")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        daily = usage.get("dailyUsageBuckets")
        if daily:
            print(f"  daily buckets: {len(daily)}")
            for row in daily[-7:]:
                print(f"    {row.get('startDate')}: {row.get('tokens')} tokens")
    else:
        print("Token usage summary: unavailable")

    if snapshot["errors"]:
        print("")
        print("Provider warnings:")
        for key, value in snapshot["errors"].items():
            print(f"  {key}: {value}")

    print("")
    print(f"Saved privacy-filtered snapshot: {latest}")
    return 0 if buckets else 3


if __name__ == "__main__":
    raise SystemExit(main())
