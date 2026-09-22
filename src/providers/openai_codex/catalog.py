from __future__ import annotations

from pathlib import Path
from typing import Any

from core import ProviderCapabilities
from .client import CodexAppServerClient


CODEX_CAPABILITIES = ProviderCapabilities(
    provider_id="openai_codex",
    account_quota=True,
    account_token_usage=True,
    rolling_quota_events=True,
    thread_token_events=True,
    model_catalog=True,
    reasoning_effort_catalog=True,
    # Passive account APIs do not identify which external client/model caused usage.
    passive_model_attribution=False,
    # Exact attribution is possible when this app-server owns the thread/turn.
    managed_thread_attribution=True,
)


def _normalize_model(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    efforts = []
    for item in value.get("supportedReasoningEfforts") or []:
        if not isinstance(item, dict):
            continue
        effort = item.get("reasoningEffort")
        if not isinstance(effort, str) or not effort:
            continue
        efforts.append(
            {
                "reasoningEffort": effort,
                "description": item.get("description"),
            }
        )

    service_tiers = []
    for item in value.get("serviceTiers") or []:
        if not isinstance(item, dict):
            continue
        tier_id = item.get("id")
        if not isinstance(tier_id, str):
            continue
        service_tiers.append(
            {
                "id": tier_id,
                "name": item.get("name"),
                "description": item.get("description"),
            }
        )

    return {
        "id": value.get("id"),
        "model": value.get("model"),
        "displayName": value.get("displayName"),
        "description": value.get("description"),
        "isDefault": bool(value.get("isDefault")),
        "hidden": bool(value.get("hidden")),
        "defaultReasoningEffort": value.get("defaultReasoningEffort"),
        "supportedReasoningEfforts": efforts,
        "defaultServiceTier": value.get("defaultServiceTier"),
        "serviceTiers": service_tiers,
    }


def read_model_catalog(
    executable: Path,
    codex_home: Path,
    *,
    include_hidden: bool = False,
) -> dict[str, Any]:
    models: list[dict[str, Any]] = []
    cursor: str | None = None

    with CodexAppServerClient(executable, codex_home) as client:
        while True:
            result = client.request(
                "model/list",
                {
                    "limit": 100,
                    "cursor": cursor,
                    "includeHidden": include_hidden,
                },
            )
            if not isinstance(result, dict):
                raise RuntimeError("model/list returned an unexpected response")

            for raw in result.get("data") or []:
                normalized = _normalize_model(raw)
                if normalized is not None:
                    models.append(normalized)

            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor

    return {
        "schemaVersion": 1,
        "provider": "openai_codex",
        "provenance": "VERIFIED",
        "capabilities": {
            "accountQuota": CODEX_CAPABILITIES.account_quota,
            "accountTokenUsage": CODEX_CAPABILITIES.account_token_usage,
            "rollingQuotaEvents": CODEX_CAPABILITIES.rolling_quota_events,
            "threadTokenEvents": CODEX_CAPABILITIES.thread_token_events,
            "modelCatalog": CODEX_CAPABILITIES.model_catalog,
            "reasoningEffortCatalog": CODEX_CAPABILITIES.reasoning_effort_catalog,
            "passiveModelAttribution": CODEX_CAPABILITIES.passive_model_attribution,
            "managedThreadAttribution": CODEX_CAPABILITIES.managed_thread_attribution,
        },
        "models": models,
    }
