from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


MAX_JSONL_LINE_BYTES = 8 * 1024 * 1024

RELEVANT_MARKERS = (
    b'"type":"session_meta"',
    b'"type": "session_meta"',
    b'"type":"turn_context"',
    b'"type": "turn_context"',
    b'"type":"token_usage_record"',
    b'"type": "token_usage_record"',
    b'"type":"event_msg"',
    b'"type": "event_msg"',
    b'"type":"selected_token_count"',
    b'"type": "selected_token_count"',
)


TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def _zero_usage() -> dict[str, int]:
    return {key: 0 for key in TOKEN_KEYS}


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and math.isfinite(value):
        return max(0, int(value))
    return 0


def _normalize_usage(value: Any) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {key: _safe_int(source.get(key)) for key in TOKEN_KEYS}


def _add_usage(target: dict[str, int], value: dict[str, int]) -> None:
    for key in TOKEN_KEYS:
        target[key] += _safe_int(value.get(key))


def _max_usage(target: dict[str, int], value: dict[str, int]) -> None:
    for key in TOKEN_KEYS:
        target[key] = max(target[key], _safe_int(value.get(key)))


def _iso_timestamp(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def _display_time(epoch: float) -> str | None:
    if epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _extract_cwd(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    direct = payload.get("cwd")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    meta = payload.get("meta")
    if isinstance(meta, dict):
        value = meta.get("cwd")
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _looks_windows_path(value: str) -> bool:
    text = value.strip()
    return (
        len(text) >= 3
        and text[1] == ":"
        and text[2] in ("\\", "/")
    ) or "\\" in text


def _normalize_project_path(cwd: str) -> str:
    text = cwd.strip()

    if _looks_windows_path(text):
        return str(PureWindowsPath(text))

    return str(PurePosixPath(text))


def _project_name(path: str) -> str:
    if _looks_windows_path(path):
        value = PureWindowsPath(path).name
    else:
        value = PurePosixPath(path).name

    return value or path


def _project_identity_key(path: str) -> str:
    if _looks_windows_path(path):
        return str(PureWindowsPath(path)).casefold()

    return str(PurePosixPath(path))


def _iter_relevant_json(path: Path):
    """Stream relevant rollout records without parsing prompt/message lines."""
    oversized = 0
    invalid = 0

    try:
        handle = path.open("rb")
    except OSError:
        return

    with handle:
        while True:
            raw = handle.readline(MAX_JSONL_LINE_BYTES + 1)
            if not raw:
                break

            if len(raw) > MAX_JSONL_LINE_BYTES and not raw.endswith(b"\n"):
                oversized += 1
                # Drain remainder of this oversized line without retaining it.
                while raw and not raw.endswith(b"\n"):
                    raw = handle.readline(MAX_JSONL_LINE_BYTES + 1)
                continue

            if not any(marker in raw for marker in RELEVANT_MARKERS):
                continue

            try:
                record = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                invalid += 1
                continue

            if isinstance(record, dict):
                yield record

    # Generator return value intentionally ignored; counters are not content.
    _ = oversized, invalid


@dataclass
class RolloutSummary:
    path: Path
    project_path: str | None = None
    project_name: str | None = None
    latest_epoch: float = 0.0
    latest_context_epoch: float = 0.0
    latest_model: str | None = None
    latest_effort: str | None = None
    thread_id: str | None = None
    response_usage: list[tuple[str, str | None, dict[str, int]]] = field(
        default_factory=list
    )
    legacy_total: dict[str, int] = field(default_factory=_zero_usage)
    turn_contexts: dict[str, tuple[float, str | None, str | None]] = field(
        default_factory=dict
    )
    transitions: list[dict[str, Any]] = field(default_factory=list)
    usage_source: str = "none"


def scan_rollout(path: Path) -> RolloutSummary:
    summary = RolloutSummary(path=path)

    response_ids: set[str] = set()
    latest_context: tuple[float, str | None, str | None] | None = None
    ordered_contexts: list[tuple[float, str, str | None, str | None]] = []

    for record in _iter_relevant_json(path):
        rtype = record.get("type")
        payload = record.get("payload")
        epoch = _iso_timestamp(record.get("timestamp"))
        summary.latest_epoch = max(summary.latest_epoch, epoch)

        if rtype == "session_meta":
            cwd = _extract_cwd(payload)
            if cwd:
                normalized = _normalize_project_path(cwd)
                summary.project_path = normalized
                summary.project_name = _project_name(normalized)

            if isinstance(payload, dict):
                for key in ("id", "session_id", "thread_id"):
                    value = payload.get(key)
                    if isinstance(value, str) and value:
                        summary.thread_id = value
                        break
                meta = payload.get("meta")
                if summary.thread_id is None and isinstance(meta, dict):
                    for key in ("id", "session_id", "thread_id"):
                        value = meta.get(key)
                        if isinstance(value, str) and value:
                            summary.thread_id = value
                            break
            continue

        if rtype == "turn_context" and isinstance(payload, dict):
            turn_id = payload.get("turn_id") or payload.get("turnId")
            model = payload.get("model")
            effort = (
                payload.get("effort")
                or payload.get("reasoning_effort")
                or payload.get("reasoningEffort")
            )

            model = model if isinstance(model, str) else None
            effort = effort if isinstance(effort, str) else None

            if isinstance(turn_id, str) and turn_id:
                summary.turn_contexts[turn_id] = (epoch, model, effort)
                ordered_contexts.append((epoch, turn_id, model, effort))

            if latest_context is None or epoch >= latest_context[0]:
                latest_context = (epoch, model, effort)
                summary.latest_context_epoch = epoch
                summary.latest_model = model
                summary.latest_effort = effort
            continue

        if rtype == "token_usage_record" and isinstance(payload, dict):
            response_id = payload.get("response_id") or payload.get("responseId")
            if not isinstance(response_id, str) or not response_id:
                continue
            if response_id in response_ids:
                continue
            response_ids.add(response_id)

            usage = _normalize_usage(payload.get("usage"))
            turn_id = payload.get("turn_id") or payload.get("turnId")
            turn_id = turn_id if isinstance(turn_id, str) else None
            summary.response_usage.append((response_id, turn_id, usage))
            continue

        info = None
        if rtype == "event_msg" and isinstance(payload, dict):
            if payload.get("type") == "token_count":
                info = payload.get("info")
        elif rtype == "selected_token_count" and isinstance(payload, dict):
            info = payload.get("info")

        if isinstance(info, dict):
            cumulative = info.get("total_token_usage")
            if isinstance(cumulative, dict):
                _max_usage(summary.legacy_total, _normalize_usage(cumulative))

    ordered_contexts.sort(key=lambda item: item[0])

    previous: tuple[str | None, str | None] | None = None
    for epoch, _turn_id, model, effort in ordered_contexts:
        current = (model, effort)
        if previous is not None and current != previous:
            summary.transitions.append(
                {
                    "observedAt": _display_time(epoch),
                    "fromModel": previous[0],
                    "fromEffort": previous[1],
                    "toModel": model,
                    "toEffort": effort,
                    "provenance": "LOCAL_OBSERVED",
                }
            )
        previous = current

    summary.usage_source = (
        "TOKEN_USAGE_RECORD"
        if summary.response_usage
        else ("LEGACY_CUMULATIVE" if any(summary.legacy_total.values()) else "none")
    )
    return summary


def _model_key(model: str | None, effort: str | None) -> str:
    return f"{model or 'unknown'}::{effort or 'unknown'}"


def _model_label(model: str | None, effort: str | None) -> str:
    return f"{model or 'unknown'} / {effort or 'unknown'}"


def _public_usage(usage: dict[str, int]) -> dict[str, Any]:
    input_tokens = usage["input_tokens"]
    cached = usage["cached_input_tokens"]
    new_input = max(input_tokens - cached, 0)
    cache_hit_rate = (cached / input_tokens) if input_tokens > 0 else None

    return {
        "inputTokens": input_tokens,
        "cachedInputTokens": cached,
        "newInputTokens": new_input,
        "cacheWriteInputTokens": usage["cache_write_input_tokens"],
        "outputTokens": usage["output_tokens"],
        "reasoningOutputTokens": usage["reasoning_output_tokens"],
        "totalTokens": usage["total_tokens"],
        "cacheHitRate": cache_hit_rate,
        "note": (
            "reasoningOutputTokens is reported separately and must not be added "
            "again to totalTokens"
        ),
    }


def aggregate_projects(
    rollouts: Iterable[RolloutSummary],
) -> list[dict[str, Any]]:
    projects: dict[str, dict[str, Any]] = {}

    for rollout in rollouts:
        if not rollout.project_path:
            continue

        project_key = _project_identity_key(rollout.project_path)
        project = projects.setdefault(
            project_key,
            {
                "projectPath": rollout.project_path,
                "projectName": rollout.project_name,
                "_usage": _zero_usage(),
                "_byModel": defaultdict(_zero_usage),
                "_latestEpoch": 0.0,
                "_latestContextEpoch": 0.0,
                "_contexts": [],
                "currentModel": None,
                "currentReasoningEffort": None,
                "threadCount": 0,
                "rolloutCount": 0,
                "modelSwitches": [],
                "usageSources": set(),
            },
        )

        project["rolloutCount"] += 1
        project["threadCount"] += 1
        project["usageSources"].add(rollout.usage_source)

        project["_latestEpoch"] = max(project["_latestEpoch"], rollout.latest_epoch)

        if rollout.latest_context_epoch >= project["_latestContextEpoch"]:
            project["_latestContextEpoch"] = rollout.latest_context_epoch
            project["currentModel"] = rollout.latest_model
            project["currentReasoningEffort"] = rollout.latest_effort

        project["_contexts"].extend(rollout.turn_contexts.values())

        if rollout.response_usage:
            for _response_id, turn_id, usage in rollout.response_usage:
                _add_usage(project["_usage"], usage)

                context = rollout.turn_contexts.get(turn_id or "")
                if context:
                    _, model, effort = context
                else:
                    model, effort = rollout.latest_model, rollout.latest_effort

                _add_usage(
                    project["_byModel"][_model_key(model, effort)],
                    usage,
                )
        else:
            _add_usage(project["_usage"], rollout.legacy_total)
            _add_usage(
                project["_byModel"][
                    _model_key(rollout.latest_model, rollout.latest_effort)
                ],
                rollout.legacy_total,
            )

    result: list[dict[str, Any]] = []

    for project in projects.values():
        model_rows = []
        for key, usage in project["_byModel"].items():
            model, effort = key.split("::", 1)
            model_rows.append(
                {
                    "model": None if model == "unknown" else model,
                    "reasoningEffort": None if effort == "unknown" else effort,
                    "label": _model_label(
                        None if model == "unknown" else model,
                        None if effort == "unknown" else effort,
                    ),
                    "usage": _public_usage(usage),
                    "provenance": "LOCAL_OBSERVED",
                }
            )

        model_rows.sort(
            key=lambda row: row["usage"]["totalTokens"],
            reverse=True,
        )

        contexts = sorted(project["_contexts"], key=lambda item: item[0])
        switches = []
        previous = None
        for epoch, model, effort in contexts:
            current = (model, effort)
            if previous is not None and current != previous:
                switches.append(
                    {
                        "observedAt": _display_time(epoch),
                        "fromModel": previous[0],
                        "fromEffort": previous[1],
                        "toModel": model,
                        "toEffort": effort,
                        "provenance": "LOCAL_OBSERVED",
                    }
                )
            previous = current

        if len(switches) > 100:
            switches = switches[-100:]

        result.append(
            {
                "projectPath": project["projectPath"],
                "projectName": project["projectName"],
                "updatedAt": _display_time(project["_latestEpoch"]),
                "currentObservedAt": _display_time(project["_latestContextEpoch"]),
                "currentModel": project["currentModel"],
                "currentReasoningEffort": project["currentReasoningEffort"],
                "usage": _public_usage(project["_usage"]),
                "byModelAndEffort": model_rows,
                "modelSwitches": switches,
                "rolloutCount": project["rolloutCount"],
                "threadCount": project["threadCount"],
                "usageSources": sorted(project["usageSources"]),
                "provenance": "LOCAL_OBSERVED",
            }
        )

    result.sort(
        key=lambda item: item["usage"]["totalTokens"],
        reverse=True,
    )
    return result


def rollout_files_for_profiles(profile_paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    for profile in profile_paths:
        for dirname in ("sessions", "archived_sessions"):
            base = profile / dirname
            if not base.is_dir():
                continue

            try:
                iterator = base.rglob("rollout-*.jsonl")
            except OSError:
                continue

            for path in iterator:
                try:
                    key = str(path.resolve()).casefold()
                except OSError:
                    key = str(path).casefold()

                if key in seen:
                    continue
                seen.add(key)
                files.append(path)

    return files


def scan_profiles(profile_paths: Iterable[Path]) -> dict[str, Any]:
    files = rollout_files_for_profiles(profile_paths)
    summaries: list[RolloutSummary] = []
    failures = 0

    for path in files:
        try:
            summaries.append(scan_rollout(path))
        except Exception:
            failures += 1

    projects = aggregate_projects(summaries)

    return {
        "schemaVersion": 1,
        "provenance": "LOCAL_OBSERVED",
        "projectUnit": "CWD_FOLDER",
        "rolloutFilesScanned": len(files),
        "rolloutFilesFailed": failures,
        "projectCount": len(projects),
        "projects": projects,
        "limitations": [
            (
                "Local rollout telemetry can undercount provider-billed usage in "
                "some Codex versions, especially auto-compaction overhead."
            ),
            (
                "Only model/effort values exposed in local turn_context records "
                "can be observed; hidden server-side routing is not inferable."
            ),
        ],
    }


