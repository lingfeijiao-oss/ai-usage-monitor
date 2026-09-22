from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex import CodexProvider  # noqa: E402
from storage import UsageStore  # noqa: E402


def local_reset_text(timestamp):
    if not isinstance(timestamp, (int, float)):
        return "unknown"
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def load_provider() -> CodexProvider:
    config_path = ROOT / "config" / "local.codex.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    return CodexProvider(
        Path(config["executable"]),
        Path(config["codex_home"]),
        codex_version=config.get("codex_version"),
    )


def snapshot_key(snapshot):
    quota = []
    for bucket in snapshot.get("quota", {}).get("buckets", []):
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if window:
                quota.append(
                    (
                        bucket.get("limitId"),
                        kind,
                        window.get("usedPercent"),
                        window.get("resetsAt"),
                    )
                )
    summary = snapshot.get("tokenUsage", {}).get("summary") or {}
    return (
        tuple(quota),
        summary.get("lifetimeTokens"),
    )


def print_snapshot(snapshot, previous=None):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] Codex", flush=True)

    for bucket in snapshot.get("quota", {}).get("buckets", []):
        name = bucket.get("limitName") or bucket.get("limitId") or "unnamed"
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if not window:
                continue
            print(
                f"  quota {name}/{kind}: "
                f"used={window.get('usedPercent')}% "
                f"remaining={window.get('remainingPercent')}% "
                f"reset={local_reset_text(window.get('resetsAt'))}",
                flush=True,
            )

    summary = snapshot.get("tokenUsage", {}).get("summary")
    if summary:
        lifetime = summary.get("lifetimeTokens")
        delta = None
        if previous:
            old = (previous.get("tokenUsage", {}).get("summary") or {}).get(
                "lifetimeTokens"
            )
            if isinstance(lifetime, int) and isinstance(old, int):
                delta = lifetime - old
        delta_text = f" delta={delta:+,}" if isinstance(delta, int) else ""
        print(f"  lifetime tokens={lifetime:,}{delta_text}", flush=True)

    if snapshot.get("errors"):
        print(f"  warnings={snapshot['errors']}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuously sample Codex usage")
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Sampling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take one sample and exit",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=0,
        help="Stop after N samples; 0 means run until Ctrl+C",
    )
    args = parser.parse_args()

    if args.interval < 5.0 and not args.once:
        parser.error("--interval must be at least 5 seconds")

    provider = load_provider()
    db_path = ROOT / "data" / "usage.sqlite3"
    previous = None
    last_key = None
    count = 0

    print("AI Usage Monitor - Codex continuous monitor")
    print(f"Database: {db_path}")
    print("Privacy: aggregate usage only; no prompts or source code.")
    print("Press Ctrl+C to stop.")
    print("")

    try:
        with UsageStore(db_path) as store:
            while True:
                started = time.monotonic()
                snapshot = provider.read_snapshot()
                store.record_snapshot(snapshot)
                key = snapshot_key(snapshot)

                # Print every first sample and whenever quota/token totals change.
                if last_key is None or key != last_key or args.once:
                    print_snapshot(snapshot, previous)
                else:
                    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
                    print(f"[{stamp}] no aggregate change", flush=True)

                previous = snapshot
                last_key = key
                count += 1

                if args.once or (args.samples > 0 and count >= args.samples):
                    break

                elapsed = time.monotonic() - started
                time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        print("")
        print("Monitor stopped.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
