from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex.tasks import (
    discover_threads,
    read_thread_usage,
    safe_task,
)


def when(value):
    if not isinstance(value, (int, float)):
        return "—"
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def main() -> int:
    cfg = json.loads(
        (ROOT / "config" / "local.codex.json").read_text(encoding="utf-8-sig")
    )

    executable = Path(cfg["executable"])
    monitor_home = Path(cfg["codex_home"])

    tasks, diagnostics = discover_threads(
        executable,
        monitor_home,
        per_home_limit=100,
    )

    print("=== Codex Task Discovery v0.9.1 ===")
    print("Profiles:")

    for row in diagnostics:
        if row["result"] == "ok":
            print(f"  {row['profile']}: {row['threadCount']} tasks")
        else:
            print(
                f"  {row['profile']}: unavailable "
                f"({row.get('errorType')})"
            )

    print("")
    print(f"Unique visible tasks: {len(tasks)}")
    print("")

    for task in tasks[:20]:
        print(task["title"])
        print(
            f"  model={task.get('model') or '—'} "
            f"effort={task.get('reasoningEffort') or '—'} "
            f"source={task.get('sourceKind') or '—'}"
        )
        print(
            f"  project={task.get('projectName') or '—'} "
            f"updated={when(task.get('updatedAt'))}"
        )

    usage_probe = None

    if tasks:
        print("")
        print("Checking official per-thread usage capability on newest task...")

        usage_probe = read_thread_usage(
            executable,
            monitor_home,
            tasks[0]["_threadId"],
        )

        print(
            f"  status={usage_probe.get('status')} "
            f"provenance={usage_probe.get('provenance')}"
        )

        if usage_probe.get("status") == "available":
            print(
                json.dumps(
                    usage_probe["threadUsage"],
                    ensure_ascii=False,
                    indent=2,
                )
            )

    safe_index = {
        "schemaVersion": 1,
        "provider": "openai_codex",
        "taskCount": len(tasks),
        "profiles": diagnostics,
        "tasks": [safe_task(task) for task in tasks[:100]],
        "usageCapabilityProbe": (
            None
            if usage_probe is None
            else {
                "status": usage_probe.get("status"),
                "provenance": usage_probe.get("provenance"),
                "reason": usage_probe.get("reason"),
            }
        ),
    }

    out = ROOT / "data" / "codex" / "task-index.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(
        json.dumps(
            safe_index,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print(f"Privacy-filtered index saved: {out}")
    print("Raw thread IDs were not persisted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
