from __future__ import annotations

from datetime import datetime
from typing import Any


class MeasurementError(ValueError):
    pass


def validate_model_effort(
    catalog: dict[str, Any],
    model: str,
    effort: str,
) -> dict[str, Any]:
    models = catalog.get("models")
    if not isinstance(models, list):
        raise MeasurementError("Model catalog is malformed")

    selected = None
    for item in models:
        if not isinstance(item, dict):
            continue
        if model in (item.get("model"), item.get("id")):
            selected = item
            break

    if selected is None:
        available = sorted(
            str(item.get("model"))
            for item in models
            if isinstance(item, dict) and item.get("model")
        )
        raise MeasurementError(
            f"Unknown model {model!r}. Available: {', '.join(available)}"
        )

    supported = [
        item.get("reasoningEffort")
        for item in selected.get("supportedReasoningEfforts") or []
        if isinstance(item, dict) and isinstance(item.get("reasoningEffort"), str)
    ]
    if effort not in supported:
        raise MeasurementError(
            f"Reasoning effort {effort!r} is not advertised for {model!r}. "
            f"Supported: {', '.join(supported)}"
        )

    return {
        "model": selected.get("model"),
        "displayName": selected.get("displayName"),
        "reasoningEffort": effort,
        "catalogProvenance": catalog.get("provenance") or "VERIFIED",
    }


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"Invalid timestamp: {value!r}") from exc


def _quota_windows(snapshot: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for bucket in snapshot.get("quota", {}).get("buckets", []) or []:
        if not isinstance(bucket, dict):
            continue
        limit_id = str(bucket.get("limitId") or "unnamed")
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if isinstance(window, dict):
                result[(limit_id, kind)] = window
    return result


def _lifetime_tokens(snapshot: dict[str, Any]) -> int | None:
    value = (
        (snapshot.get("tokenUsage") or {})
        .get("summary", {})
        .get("lifetimeTokens")
    )
    return value if isinstance(value, int) else None


def build_measurement_result(
    start_snapshot: dict[str, Any],
    end_snapshot: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    label: str | None = None,
) -> dict[str, Any]:
    start_at = _parse_time(str(start_snapshot["observedAt"]))
    end_at = _parse_time(str(end_snapshot["observedAt"]))
    elapsed = max(0.0, (end_at - start_at).total_seconds())

    start_tokens = _lifetime_tokens(start_snapshot)
    end_tokens = _lifetime_tokens(end_snapshot)
    token_delta = None
    if start_tokens is not None and end_tokens is not None:
        token_delta = end_tokens - start_tokens

    start_windows = _quota_windows(start_snapshot)
    end_windows = _quota_windows(end_snapshot)
    quota_deltas: list[dict[str, Any]] = []

    for key in sorted(set(start_windows) | set(end_windows)):
        start = start_windows.get(key)
        end = end_windows.get(key)
        if start is None or end is None:
            quota_deltas.append(
                {
                    "limitId": key[0],
                    "windowKind": key[1],
                    "comparable": False,
                    "reason": "window_missing_at_one_boundary",
                }
            )
            continue

        same_reset = start.get("resetsAt") == end.get("resetsAt")
        same_duration = (
            start.get("windowDurationMins") == end.get("windowDurationMins")
        )
        comparable = same_reset and same_duration

        used_delta = None
        if comparable:
            before = start.get("usedPercent")
            after = end.get("usedPercent")
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                used_delta = float(after) - float(before)

        quota_deltas.append(
            {
                "limitId": key[0],
                "windowKind": key[1],
                "comparable": comparable,
                "reason": None if comparable else "quota_window_changed_or_reset",
                "startUsedPercent": start.get("usedPercent"),
                "endUsedPercent": end.get("usedPercent"),
                "usedPercentDelta": used_delta,
                "startResetsAt": start.get("resetsAt"),
                "endResetsAt": end.get("resetsAt"),
            }
        )

    ratios = []
    if isinstance(token_delta, int) and token_delta >= 0:
        for quota in quota_deltas:
            delta = quota.get("usedPercentDelta")
            if isinstance(delta, (int, float)) and delta > 0:
                ratios.append(
                    {
                        "limitId": quota["limitId"],
                        "windowKind": quota["windowKind"],
                        "tokensPerObservedQuotaPercent": token_delta / float(delta),
                        "provenance": "ESTIMATED",
                    }
                )

    return {
        "schemaVersion": 1,
        "provider": "openai_codex",
        "attributionScope": "ACCOUNT_EXCLUSIVE_WINDOW",
        "attributionProvenance": "OBSERVED",
        "attributionCaveat": (
            "Token/quota deltas include all account activity during this measurement "
            "window. Exact attribution requires a managed App Server thread."
        ),
        "label": label,
        "model": model,
        "reasoningEffort": reasoning_effort,
        "startedAt": start_snapshot["observedAt"],
        "endedAt": end_snapshot["observedAt"],
        "elapsedSeconds": elapsed,
        "startLifetimeTokens": start_tokens,
        "endLifetimeTokens": end_tokens,
        "tokenDelta": token_delta,
        "quotaDeltas": quota_deltas,
        "derivedRatios": ratios,
    }
