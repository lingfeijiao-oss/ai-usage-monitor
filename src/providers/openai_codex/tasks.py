from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from core.codex_discovery import discover_profiles

from .client import CodexAppServerClient, JsonRpcError


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def discover_codex_homes(
    monitor_home: Path,
    *,
    extra: list[Path] | None = None,
) -> list[Path]:
    candidates: list[Path] = []

    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        candidates.append(Path(env_home))

    candidates.extend(
        Path(profile.path)
        for profile in discover_profiles()
    )

    candidates.append(
        Path(monitor_home)
    )

    if extra:
        candidates.extend(extra)

    result: list[Path] = []
    seen: set[str] = set()

    for path in candidates:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()

        if key in seen:
            continue
        seen.add(key)

        if path.is_dir():
            result.append(path)

    return result


def _source_kind(source: Any) -> str | None:
    if isinstance(source, str):
        return source
    if isinstance(source, dict):
        kind = source.get("type")
        if isinstance(kind, str):
            return kind
    return None


def _looks_windows_path(value: str) -> bool:
    text = value.strip()
    return (
        len(text) >= 3
        and text[1] == ":"
        and text[2] in ("\\", "/")
    ) or "\\" in text


def _project_name(cwd: Any) -> str | None:
    if not isinstance(cwd, str) or not cwd.strip():
        return None

    text = cwd.strip()

    try:
        if _looks_windows_path(text):
            return PureWindowsPath(text).name or None

        return PurePosixPath(text).name or None

    except (OSError, ValueError):
        return None


def normalize_thread(
    thread: Any,
    profile_home: Path,
) -> dict[str, Any] | None:
    if not isinstance(thread, dict):
        return None

    thread_id = thread.get("id")
    if not isinstance(thread_id, str) or not thread_id:
        return None

    name = thread.get("name")
    preview = thread.get("preview")

    if isinstance(name, str) and name.strip():
        title = name.strip()
        title_source = "name"
    elif isinstance(preview, str) and preview.strip():
        title = preview.strip().replace("\r", " ").replace("\n", " ")
        if len(title) > 120:
            title = title[:117] + "..."
        title_source = "preview"
    else:
        title = "Untitled Codex task"
        title_source = "fallback"

    return {
        "_threadId": thread_id,
        "threadIdHash": hash_identifier(thread_id),
        "title": title,
        "titleSource": title_source,
        "model": thread.get("model"),
        "reasoningEffort": thread.get("reasoningEffort"),
        "modelProvider": thread.get("modelProvider"),
        "sourceKind": _source_kind(thread.get("source")),
        "createdAt": thread.get("createdAt"),
        "updatedAt": thread.get("updatedAt"),
        "ephemeral": bool(thread.get("ephemeral")),
        "isPinned": bool(thread.get("isPinned")),
        "projectName": _project_name(thread.get("cwd")),
        "profileName": profile_home.name,
        "status": thread.get("status"),
    }


def list_threads_from_home(
    executable: Path,
    codex_home: Path,
    *,
    limit: int = 100,
    archived: bool = False,
    timeout_seconds: float = 15.0,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    rows: list[dict[str, Any]] = []
    cursor: str | None = None

    with CodexAppServerClient(
        executable,
        codex_home,
        timeout_seconds=timeout_seconds,
    ) as client:
        while len(rows) < limit:
            page_size = min(100, limit - len(rows))

            # Keep this request deliberately minimal. useStateDbOnly avoids
            # triggering the default JSONL scan/metadata-repair discovery path.
            params: dict[str, Any] = {
                "limit": page_size,
                "archived": archived,
                "useStateDbOnly": True,
            }
            if cursor:
                params["cursor"] = cursor

            result = client.request("thread/list", params)
            if not isinstance(result, dict):
                break

            for raw in result.get("data") or []:
                item = normalize_thread(raw, codex_home)
                if item is not None:
                    rows.append(item)
                    if len(rows) >= limit:
                        break

            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor

    # Sort locally so the product does not depend on optional server sort args.
    rows.sort(
        key=lambda row: (
            row.get("updatedAt")
            if isinstance(row.get("updatedAt"), (int, float))
            else -1
        ),
        reverse=True,
    )
    return rows


def discover_threads(
    executable: Path,
    monitor_home: Path,
    *,
    per_home_limit: int = 100,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    homes = discover_codex_homes(monitor_home)
    combined: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []

    for home in homes:
        try:
            rows = list_threads_from_home(
                executable,
                home,
                limit=per_home_limit,
                archived=False,
            )
            diagnostics.append(
                {
                    "profile": str(home),
                    "result": "ok",
                    "threadCount": len(rows),
                }
            )

            for row in rows:
                thread_id = row["_threadId"]
                current = combined.get(thread_id)

                if current is None:
                    combined[thread_id] = row
                    continue

                current_updated = current.get("updatedAt")
                candidate_updated = row.get("updatedAt")

                if isinstance(candidate_updated, (int, float)) and (
                    not isinstance(current_updated, (int, float))
                    or candidate_updated > current_updated
                ):
                    combined[thread_id] = row

        except Exception as exc:
            diagnostics.append(
                {
                    "profile": str(home),
                    "result": "unavailable",
                    "errorType": type(exc).__name__,
                }
            )

    tasks = list(combined.values())
    tasks.sort(
        key=lambda row: (
            row.get("updatedAt")
            if isinstance(row.get("updatedAt"), (int, float))
            else -1
        ),
        reverse=True,
    )

    return tasks, diagnostics


def safe_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in task.items()
        if key != "_threadId"
    }


def read_thread_usage(
    executable: Path,
    authenticated_home: Path,
    thread_id: str,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    """Request the provider's per-thread usage estimate.

    This is not locally inferred from account totals. If the provider returns
    no threadUsage object, the caller must show it as unavailable.
    """
    with CodexAppServerClient(
        executable,
        authenticated_home,
        timeout_seconds=timeout_seconds,
    ) as client:
        try:
            result = client.request(
                "account/usage/read",
                {"threadId": thread_id},
            )
        except JsonRpcError as exc:
            if exc.code in (-32600, -32601, -32602):
                return {
                    "status": "unsupported_server",
                    "provenance": "UNSUPPORTED",
                    "errorCode": exc.code,
                }
            raise

    if not isinstance(result, dict):
        return {
            "status": "unexpected_response",
            "provenance": "UNSUPPORTED",
        }

    usage = result.get("threadUsage")

    if usage is None:
        return {
            "status": "unavailable",
            "provenance": "OFFICIAL_UNAVAILABLE",
            "reason": "provider_did_not_return_thread_usage",
        }

    if not isinstance(usage, dict):
        return {
            "status": "unexpected_thread_usage",
            "provenance": "UNSUPPORTED",
        }

    return {
        "status": "available",
        "provenance": "OFFICIAL_ESTIMATE",
        "threadUsage": usage,
    }


