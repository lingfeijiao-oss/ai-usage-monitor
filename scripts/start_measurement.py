from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analytics import MeasurementError, validate_model_effort  # noqa: E402
from providers.openai_codex import CodexProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start an observed Codex usage measurement window"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    catalog = json.loads(
        (ROOT / "data" / "codex" / "model-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        selection = validate_model_effort(catalog, args.model, args.effort)
    except MeasurementError as exc:
        print(f"ERROR: {exc}")
        return 2

    cfg = json.loads(
        (ROOT / "config" / "local.codex.json").read_text(encoding="utf-8-sig")
    )
    provider = CodexProvider(
        Path(cfg["executable"]),
        Path(cfg["codex_home"]),
        codex_version=cfg.get("codex_version"),
    )
    snapshot = provider.read_snapshot()

    session_id = uuid.uuid4().hex[:16]
    session = {
        "schemaVersion": 1,
        "sessionId": session_id,
        "state": "open",
        "attributionScope": "ACCOUNT_EXCLUSIVE_WINDOW",
        "attributionProvenance": "OBSERVED",
        "selection": selection,
        "label": args.label,
        "startSnapshot": snapshot,
    }

    path = ROOT / "data" / "measurements" / f"{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Measurement started ===")
    print(f"Session: {session_id}")
    print(f"Model:   {selection['displayName'] or selection['model']}")
    print(f"Effort:  {selection['reasoningEffort']}")
    print("Scope:   ACCOUNT_EXCLUSIVE_WINDOW [OBSERVED]")
    print("")
    print(
        "For meaningful attribution, avoid other Codex activity on the same "
        "account until this measurement is stopped."
    )
    print("")
    print("Stop with:")
    print(
        f'  py -3 "{ROOT}\\scripts\\stop_measurement.py" '
        f'--session {session_id}'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
