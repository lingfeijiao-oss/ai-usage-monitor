from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MetricProvenance(StrEnum):
    VERIFIED = "VERIFIED"
    OBSERVED = "OBSERVED"
    ESTIMATED = "ESTIMATED"
    UNSUPPORTED = "UNSUPPORTED"


class AttributionScope(StrEnum):
    ACCOUNT_PASSIVE = "ACCOUNT_PASSIVE"
    LOCAL_APP_SERVER_THREAD = "LOCAL_APP_SERVER_THREAD"
    MANAGED_THREAD = "MANAGED_THREAD"


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    account_quota: bool
    account_token_usage: bool
    rolling_quota_events: bool
    thread_token_events: bool
    model_catalog: bool
    reasoning_effort_catalog: bool
    passive_model_attribution: bool
    managed_thread_attribution: bool
