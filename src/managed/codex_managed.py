from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from analytics import validate_model_effort


class ManagedRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagedRunSpec:
    model: str
    reasoning_effort: str
    prompt: str
    cwd: str
    sandbox: str = "read-only"
    timeout_seconds: float = 120.0

    def public_metadata(self) -> dict[str, Any]:
        # Prompt text is intentionally excluded from persisted metadata.
        data = asdict(self)
        data.pop("prompt", None)
        data["promptCharacterCount"] = len(self.prompt)
        return data


def quota_allows_managed_run(snapshot: dict[str, Any]) -> tuple[bool, str]:
    quota = snapshot.get("quota") or {}
    if quota.get("ordinaryUsageAllowed") is False:
        return False, "ordinaryUsageAllowed=false"

    buckets = quota.get("buckets") or []
    if not buckets:
        return False, "no verified quota bucket"

    any_window = False
    for bucket in buckets:
        for kind in ("primary", "secondary"):
            window = bucket.get(kind)
            if not isinstance(window, dict):
                continue
            any_window = True
            remaining = window.get("remainingPercent")
            if isinstance(remaining, (int, float)) and remaining <= 0:
                return False, (
                    f"{bucket.get('limitId') or 'unnamed'}/{kind} "
                    "has no remaining quota"
                )

    if not any_window:
        return False, "no comparable quota window"

    return True, "quota available"


def build_dry_run_plan(
    catalog: dict[str, Any],
    spec: ManagedRunSpec,
) -> dict[str, Any]:
    selection = validate_model_effort(
        catalog,
        spec.model,
        spec.reasoning_effort,
    )
    if spec.sandbox not in {"read-only", "workspace-write"}:
        raise ManagedRunError(
            "Managed measurement only permits read-only or workspace-write sandbox"
        )
    if spec.timeout_seconds <= 0:
        raise ManagedRunError("timeout_seconds must be positive")
    if not spec.prompt.strip():
        raise ManagedRunError("prompt must not be empty")

    return {
        "schemaVersion": 1,
        "provider": "openai_codex",
        "mode": "MANAGED_THREAD",
        "executionRequested": False,
        "selection": selection,
        "spec": spec.public_metadata(),
        "privacy": {
            "persistPrompt": False,
            "persistThreadId": False,
            "persistTurnId": False,
            "persistSourceCode": False,
        },
        "measurement": {
            "model": "VERIFIED",
            "reasoningEffort": "VERIFIED",
            "threadTokenUsage": "VERIFIED",
            "elapsedTime": "OBSERVED",
            "accountQuotaBeforeAfter": "VERIFIED",
            "quotaDeltaAttribution": "OBSERVED",
        },
    }
