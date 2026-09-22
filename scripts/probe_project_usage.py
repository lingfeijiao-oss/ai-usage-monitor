from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analytics.project_usage import scan_profiles  # noqa: E402
from core.codex_discovery import (  # noqa: E402
    discover_installations,
    discover_profiles,
)


def fmt(value):
    if not isinstance(value, int):
        return "—"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,}"


def pct(value):
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value * 100:.1f}%"


def main() -> int:
    installs = discover_installations(allow_fallback_scan=False)
    profiles = discover_profiles(installs)
    paths = [Path(item.path) for item in profiles]

    print("=== Project Usage Probe v1.1 ===")
    print("Project unit: working directory folder (cwd)")
    print("Profiles:")
    for path in paths:
        print(f"  {path}")
    print("")

    report = scan_profiles(paths)

    print(f"Rollout files scanned: {report['rolloutFilesScanned']}")
    print(f"Rollout files failed:  {report['rolloutFilesFailed']}")
    print(f"Projects found:         {report['projectCount']}")
    print("")

    for project in report["projects"][:20]:
        usage = project["usage"]
        print(project["projectName"])
        print(f"  folder:    {project['projectPath']}")
        print(
            f"  current:   {project.get('currentModel') or '—'} / "
            f"{project.get('currentReasoningEffort') or '—'}"
        )
        print(
            f"  tokens:    total={fmt(usage['totalTokens'])} "
            f"input={fmt(usage['inputTokens'])} "
            f"cached={fmt(usage['cachedInputTokens'])} "
            f"new={fmt(usage['newInputTokens'])}"
        )
        print(
            f"             output={fmt(usage['outputTokens'])} "
            f"reasoning={fmt(usage['reasoningOutputTokens'])} "
            f"cache-hit={pct(usage['cacheHitRate'])}"
        )

        if project["byModelAndEffort"]:
            print("  model/effort:")
            for row in project["byModelAndEffort"][:8]:
                print(
                    f"    {row['label']}: "
                    f"{fmt(row['usage']['totalTokens'])}"
                )

        if project["modelSwitches"]:
            last = project["modelSwitches"][-1]
            print(
                "  latest switch: "
                f"{last.get('fromModel')}/{last.get('fromEffort')} -> "
                f"{last.get('toModel')}/{last.get('toEffort')}"
            )
        print("")

    out = ROOT / "data" / "projects" / "project-usage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved local aggregate: {out}")
    print("")
    print("Provenance: LOCAL_OBSERVED")
    print(
        "No prompt/response/source-code body is persisted by this scanner."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
