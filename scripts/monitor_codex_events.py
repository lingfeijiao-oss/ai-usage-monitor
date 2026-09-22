from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.client import CodexAppServerClient, JsonRpcError  # noqa: E402
from providers.openai_codex.event_normalizer import (  # noqa: E402
    normalize_rate_limit_event,
    normalize_thread_token_event,
)
from providers.openai_codex.provider import (  # noqa: E402
    normalize_rate_limits,
    normalize_usage,
)
from storage import UsageStore  # noqa: E402


PROVIDER = "openai_codex"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_reset_text(timestamp):
    if not isinstance(timestamp, (int, float)):
        return "unknown"
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def config():
    return json.loads(
        (ROOT / "config" / "local.codex.json").read_text(encoding="utf-8-sig")
    )


def read_full_snapshot(client, codex_version):
    errors = {}

    try:
        account_result = client.request("account/read", {"refreshToken": False})
    except Exception as exc:
        account_result = {}
        errors["account"] = str(exc)

    try:
        try:
            raw_rate = client.request(
                "account/rateLimits/read",
                {"supportsLunaReserve": True},
            )
        except JsonRpcError as exc:
            if exc.code not in (-32600, -32602):
                raise
            raw_rate = client.request("account/rateLimits/read")
        quota = normalize_rate_limits(raw_rate)
    except Exception as exc:
        quota = {
            "provenance": "UNSUPPORTED",
            "ordinaryUsageAllowed": None,
            "buckets": [],
            "rateLimitResetCredits": None,
        }
        errors["rateLimits"] = str(exc)

    try:
        usage = normalize_usage(client.request("account/usage/read"))
    except Exception as exc:
        usage = {
            "provenance": "UNSUPPORTED",
            "summary": None,
            "dailyUsageBuckets": None,
            "threadUsage": None,
        }
        errors["tokenUsage"] = str(exc)

    account = account_result.get("account") if isinstance(account_result, dict) else None
    return {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "observedAt": utc_now(),
        "codexVersion": codex_version,
        "account": {
            "provenance": "VERIFIED" if isinstance(account, dict) else "UNSUPPORTED",
            "type": account.get("type") if isinstance(account, dict) else None,
            "planType": account.get("planType") if isinstance(account, dict) else None,
        },
        "quota": quota,
        "tokenUsage": usage,
        "errors": errors,
    }


def print_account_snapshot(snapshot, previous_lifetime=None):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{stamp}] ACCOUNT SNAPSHOT", flush=True)

    for bucket in snapshot.get("quota", {}).get("buckets", []):
        name = bucket.get("limitName") or bucket.get("limitId") or "unnamed"
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if not window:
                continue
            print(
                f"  {name}/{kind}: used={window.get('usedPercent')}% "
                f"remaining={window.get('remainingPercent')}% "
                f"reset={local_reset_text(window.get('resetsAt'))}",
                flush=True,
            )

    summary = snapshot.get("tokenUsage", {}).get("summary") or {}
    lifetime = summary.get("lifetimeTokens")
    if isinstance(lifetime, int):
        delta = None
        if isinstance(previous_lifetime, int):
            delta = lifetime - previous_lifetime
        suffix = f" observed_delta={delta:+,}" if isinstance(delta, int) else ""
        print(f"  lifetimeTokens={lifetime:,}{suffix}", flush=True)
    return lifetime


def main():
    parser = argparse.ArgumentParser(
        description="Persistent Codex account/event monitor"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=30.0,
        help="Fallback full account refresh interval in seconds (default 30)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Exit after N seconds; 0 means run until Ctrl+C",
    )
    args = parser.parse_args()

    if args.poll_interval < 5:
        parser.error("--poll-interval must be at least 5 seconds")

    cfg = config()
    db_path = ROOT / "data" / "usage.sqlite3"
    executable = Path(cfg["executable"])
    codex_home = Path(cfg["codex_home"])

    print("AI Usage Monitor - Codex Event Monitor v0.3")
    print("Account quota: VERIFIED account snapshot + rolling event trigger")
    print("Account tokens: VERIFIED account aggregate")
    print("Thread tokens: VERIFIED only for threads visible to THIS app-server")
    print("No prompts, source code, account IDs, thread IDs or turn IDs are persisted.")
    print(f"Database: {db_path}")
    print("")

    started = time.monotonic()
    next_poll = started
    previous_lifetime = None

    with UsageStore(db_path) as store:
        with CodexAppServerClient(executable, codex_home) as client:
            try:
                while True:
                    now = time.monotonic()
                    if args.duration > 0 and now - started >= args.duration:
                        break

                    if now >= next_poll:
                        snapshot = read_full_snapshot(
                            client, cfg.get("codex_version")
                        )
                        store.record_snapshot(snapshot)
                        previous_lifetime = print_account_snapshot(
                            snapshot, previous_lifetime
                        )
                        next_poll = now + args.poll_interval

                    wait = max(0.05, min(1.0, next_poll - time.monotonic()))
                    notification = client.next_notification(timeout=wait)
                    if not notification:
                        continue

                    method = notification.get("method")
                    params = notification.get("params")
                    observed_at = utc_now()

                    if method == "account/rateLimits/updated":
                        event = normalize_rate_limit_event(params)
                        if event is not None:
                            store.record_event(
                                observed_at, PROVIDER, method, event
                            )
                            print(
                                f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] "
                                "EVENT account/rateLimits/updated -> refreshing full quota",
                                flush=True,
                            )
                            # Rolling updates are sparse; always refresh canonical snapshot.
                            snapshot = read_full_snapshot(
                                client, cfg.get("codex_version")
                            )
                            store.record_snapshot(snapshot)
                            previous_lifetime = print_account_snapshot(
                                snapshot, previous_lifetime
                            )
                            next_poll = time.monotonic() + args.poll_interval
                        continue

                    if method == "thread/tokenUsage/updated":
                        event = normalize_thread_token_event(params)
                        if event is not None:
                            store.record_thread_token_event(
                                observed_at, PROVIDER, event
                            )
                            last = event.get("last") or {}
                            print(
                                f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] "
                                "EVENT thread/tokenUsage/updated "
                                f"scope={event['scope']} "
                                f"last_total={last.get('totalTokens')} "
                                f"input={last.get('inputTokens')} "
                                f"cached={last.get('cachedInputTokens')} "
                                f"output={last.get('outputTokens')} "
                                f"reasoning={last.get('reasoningOutputTokens')}",
                                flush=True,
                            )
                        continue

                    # Only persist method name, never raw payload, for unrelated events.
                    if isinstance(method, str):
                        store.record_event(
                            observed_at,
                            PROVIDER,
                            "notification_seen",
                            {"method": method},
                        )

            except KeyboardInterrupt:
                print("")
                print("Monitor stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
