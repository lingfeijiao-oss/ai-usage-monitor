from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analytics import build_measurement_result  # noqa: E402
from providers.openai_codex import CodexProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop a Codex measurement window")
    parser.add_argument("--session", required=True)
    args = parser.parse_args()

    path = ROOT / "data" / "measurements" / f"{args.session}.json"
    if not path.is_file():
        print(f"ERROR: unknown session {args.session}")
        return 2

    session = json.loads(path.read_text(encoding="utf-8"))
    if session.get("state") != "open":
        print("ERROR: measurement is already closed")
        return 3

    cfg = json.loads(
        (ROOT / "config" / "local.codex.json").read_text(encoding="utf-8-sig")
    )
    provider = CodexProvider(
        Path(cfg["executable"]),
        Path(cfg["codex_home"]),
        codex_version=cfg.get("codex_version"),
    )
    end_snapshot = provider.read_snapshot()

    selection = session["selection"]
    result = build_measurement_result(
        session["startSnapshot"],
        end_snapshot,
        model=selection["model"],
        reasoning_effort=selection["reasoningEffort"],
        label=session.get("label"),
    )

    session["state"] = "closed"
    session["endSnapshot"] = end_snapshot
    session["result"] = result
    path.write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Measurement result ===")
    print(f"Session: {args.session}")
    print(f"Model:   {result['model']}")
    print(f"Effort:  {result['reasoningEffort']}")
    print(f"Elapsed: {result['elapsedSeconds']:.1f} sec")
    print(f"Tokens:  {result['tokenDelta']}")
    print("Scope:   ACCOUNT_EXCLUSIVE_WINDOW [OBSERVED]")
    print("")

    for quota in result["quotaDeltas"]:
        if quota["comparable"]:
            print(
                f"{quota['limitId']}/{quota['windowKind']}: "
                f"{quota['startUsedPercent']}% -> {quota['endUsedPercent']}% "
                f"(delta {quota['usedPercentDelta']:+.3f} pp)"
            )
        else:
            print(
                f"{quota['limitId']}/{quota['windowKind']}: "
                f"not comparable ({quota['reason']})"
            )

    if result["derivedRatios"]:
        print("")
        print("Derived ratios [ESTIMATED]")
        for row in result["derivedRatios"]:
            print(
                f"  {row['limitId']}/{row['windowKind']}: "
                f"{row['tokensPerObservedQuotaPercent']:.0f} "
                "tokens per observed quota percentage point"
            )

    print("")
    print(f"Saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
