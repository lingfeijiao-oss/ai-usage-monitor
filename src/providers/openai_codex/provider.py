from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import CodexAppServerClient, JsonRpcError


def _iso_from_unix(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _normalize_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    used = value.get("usedPercent")
    remaining = None
    if isinstance(used, (int, float)):
        remaining = max(0.0, min(100.0, 100.0 - float(used)))

    result = {
        "usedPercent": used,
        "remainingPercent": remaining,
        "windowDurationMins": value.get("windowDurationMins"),
        "resetsAt": value.get("resetsAt"),
        "resetsAtUtc": _iso_from_unix(value.get("resetsAt")),
    }
    return result


def _normalize_credits(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = ("hasCredits", "unlimited", "balance")
    result = {key: value.get(key) for key in allowed if key in value}
    return result or None


def _normalize_individual_limit(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result = {
        key: value.get(key)
        for key in ("limit", "used", "remainingPercent", "resetsAt")
        if key in value
    }
    if "resetsAt" in result:
        result["resetsAtUtc"] = _iso_from_unix(result["resetsAt"])
    return result or None


def _normalize_bucket(value: Any, fallback_id: str | None = None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "limitId": source.get("limitId") or fallback_id,
        "limitName": source.get("limitName"),
        "normalModelSlug": source.get("normalModelSlug"),
        "planType": source.get("planType"),
        "primary": _normalize_window(source.get("primary")),
        "secondary": _normalize_window(source.get("secondary")),
        "credits": _normalize_credits(source.get("credits")),
        "individualLimit": _normalize_individual_limit(source.get("individualLimit")),
        "rateLimitReachedType": source.get("rateLimitReachedType"),
    }


def normalize_rate_limits(result: Any) -> dict[str, Any]:
    source = result if isinstance(result, dict) else {}
    by_id = source.get("rateLimitsByLimitId")

    buckets: list[dict[str, Any]] = []
    if isinstance(by_id, dict) and by_id:
        for limit_id, bucket in sorted(by_id.items()):
            buckets.append(_normalize_bucket(bucket, str(limit_id)))
    elif isinstance(source.get("rateLimits"), dict):
        buckets.append(_normalize_bucket(source["rateLimits"]))

    reset_credits = source.get("rateLimitResetCredits")
    reset_summary = None
    if isinstance(reset_credits, dict):
        reset_summary = {
            "availableCount": reset_credits.get("availableCount"),
        }

    return {
        "provenance": "VERIFIED",
        "ordinaryUsageAllowed": source.get("ordinaryUsageAllowed"),
        "buckets": buckets,
        "rateLimitResetCredits": reset_summary,
    }


def normalize_usage(result: Any) -> dict[str, Any]:
    source = result if isinstance(result, dict) else {}
    summary = source.get("summary")
    daily = source.get("dailyUsageBuckets")

    safe_summary = None
    if isinstance(summary, dict):
        safe_summary = {
            key: summary.get(key)
            for key in (
                "lifetimeTokens",
                "peakDailyTokens",
                "longestRunningTurnSec",
                "currentStreakDays",
                "longestStreakDays",
            )
            if key in summary
        }

    safe_daily: list[dict[str, Any]] | None = None
    if isinstance(daily, list):
        safe_daily = []
        for row in daily:
            if isinstance(row, dict):
                safe_daily.append(
                    {
                        "startDate": row.get("startDate"),
                        "tokens": row.get("tokens"),
                    }
                )

    thread_usage = source.get("threadUsage")
    safe_thread = None
    if isinstance(thread_usage, dict):
        # Keep only aggregate token counters, never prompt/message content.
        safe_thread = {
            key: thread_usage.get(key)
            for key in (
                "totalTokens",
                "inputTokens",
                "cachedInputTokens",
                "outputTokens",
                "reasoningOutputTokens",
            )
            if key in thread_usage
        }

    return {
        "provenance": "VERIFIED",
        "summary": safe_summary,
        "dailyUsageBuckets": safe_daily,
        "threadUsage": safe_thread,
    }


class CodexProvider:
    provider_id = "openai_codex"

    def __init__(
        self,
        executable: Path,
        codex_home: Path,
        *,
        codex_version: str | None = None,
    ) -> None:
        self.executable = Path(executable)
        self.codex_home = Path(codex_home)
        self.codex_version = codex_version

    def read_snapshot(self) -> dict[str, Any]:
        errors: dict[str, str] = {}

        with CodexAppServerClient(self.executable, self.codex_home) as client:
            account_result: Any = {}
            try:
                account_result = client.request(
                    "account/read", {"refreshToken": False}
                )
            except Exception as exc:
                errors["account"] = str(exc)

            try:
                try:
                    rate_result = client.request(
                        "account/rateLimits/read",
                        {"supportsLunaReserve": True},
                    )
                except JsonRpcError as exc:
                    if exc.code not in (-32600, -32602):
                        raise
                    rate_result = client.request("account/rateLimits/read")
                quota = normalize_rate_limits(rate_result)
            except Exception as exc:
                quota = {
                    "provenance": "UNSUPPORTED",
                    "ordinaryUsageAllowed": None,
                    "buckets": [],
                    "rateLimitResetCredits": None,
                }
                errors["rateLimits"] = str(exc)

            try:
                usage_result = client.request("account/usage/read")
                token_usage = normalize_usage(usage_result)
            except Exception as exc:
                token_usage = {
                    "provenance": "UNSUPPORTED",
                    "summary": None,
                    "dailyUsageBuckets": None,
                    "threadUsage": None,
                }
                errors["tokenUsage"] = str(exc)

        account = account_result.get("account") if isinstance(account_result, dict) else None
        safe_account = {
            "provenance": "VERIFIED" if isinstance(account, dict) else "UNSUPPORTED",
            "type": account.get("type") if isinstance(account, dict) else None,
            "planType": account.get("planType") if isinstance(account, dict) else None,
        }

        return {
            "schemaVersion": 1,
            "provider": self.provider_id,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "codexVersion": self.codex_version,
            "account": safe_account,
            "quota": quota,
            "tokenUsage": token_usage,
            "errors": errors,
        }
