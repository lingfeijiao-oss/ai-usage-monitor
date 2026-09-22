from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .project_usage import (
    RolloutSummary,
    aggregate_projects,
    rollout_files_for_profiles,
    scan_rollout,
)


@dataclass(frozen=True)
class FileSignature:
    size: int
    mtime_ns: int


class ProjectUsageWatcher:
    """Incremental in-process watcher for Codex rollout telemetry.

    First refresh scans all rollout files. Later refreshes parse only files whose
    size or modification time changed, plus newly created files.
    """

    def __init__(self, profile_paths: Iterable[Path]) -> None:
        self.profile_paths = [Path(path) for path in profile_paths]
        self._cache: dict[str, tuple[FileSignature, RolloutSummary]] = {}
        self.failures = 0

    def refresh(self) -> dict:
        paths = rollout_files_for_profiles(self.profile_paths)
        live_keys: set[str] = set()
        failures = 0

        for path in paths:
            try:
                key = str(path.resolve()).casefold()
            except OSError:
                key = str(path).casefold()

            live_keys.add(key)

            try:
                stat = path.stat()
            except OSError:
                failures += 1
                continue

            signature = FileSignature(
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )

            cached = self._cache.get(key)
            if cached is not None and cached[0] == signature:
                continue

            try:
                summary = scan_rollout(path)
            except Exception:
                failures += 1
                continue

            self._cache[key] = (signature, summary)

        stale = [key for key in self._cache if key not in live_keys]
        for key in stale:
            self._cache.pop(key, None)

        self.failures = failures
        summaries = [item[1] for item in self._cache.values()]
        projects = aggregate_projects(summaries)

        return {
            "projectCount": len(projects),
            "rolloutCount": len(summaries),
            "failed": failures,
            "projects": projects,
        }
