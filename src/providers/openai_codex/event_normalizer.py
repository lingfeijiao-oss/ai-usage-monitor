from __future__ import annotations

from typing import Any


def normalize_thread_token_event(params: Any) -> dict[str, Any] | None:
    """Privacy-filter a thread/tokenUsage/updated notification.

    Thread and turn IDs are intentionally not persisted. They are only reduced
    to a boolean presence signal because v0.3 is a usage monitor, not a
    conversation/session archive.
    """
    if not isinstance(params, dict):
        return None

    usage = params.get("tokenUsage")
    if not isinstance(usage, dict):
        return None

    def clean_breakdown(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        keys = (
            "inputTokens",
            "cachedInputTokens",
            "cacheWriteInputTokens",
            "outputTokens",
            "reasoningOutputTokens",
            "totalTokens",
        )
        result: dict[str, int] = {}
        for key in keys:
            item = value.get(key)
            if isinstance(item, int):
                result[key] = item
        return result or None

    return {
        "provenance": "VERIFIED",
        "scope": "LOCAL_APP_SERVER_THREAD",
        "threadIdPresent": isinstance(params.get("threadId"), str),
        "turnIdPresent": isinstance(params.get("turnId"), str),
        "modelContextWindow": usage.get("modelContextWindow"),
        "last": clean_breakdown(usage.get("last")),
        "total": clean_breakdown(usage.get("total")),
    }


def normalize_rate_limit_event(params: Any) -> dict[str, Any] | None:
    if not isinstance(params, dict):
        return None
    rate_limits = params.get("rateLimits")
    if not isinstance(rate_limits, dict):
        return None

    # Rolling notifications are sparse. They are only used as a trigger for a
    # full account/rateLimits/read refresh; this summary is diagnostic only.
    return {
        "provenance": "VERIFIED",
        "scope": "ACCOUNT_ROLLING_NOTIFICATION",
        "limitId": rate_limits.get("limitId"),
        "hasPrimary": isinstance(rate_limits.get("primary"), dict),
        "hasSecondary": isinstance(rate_limits.get("secondary"), dict),
        "rateLimitReachedType": rate_limits.get("rateLimitReachedType"),
    }
