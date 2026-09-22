from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from providers.openai_codex import CODEX_CAPABILITIES, read_model_catalog  # noqa: E402


def main() -> int:
    cfg = json.loads(
        (ROOT / "config" / "local.codex.json").read_text(encoding="utf-8-sig")
    )

    catalog = read_model_catalog(
        Path(cfg["executable"]),
        Path(cfg["codex_home"]),
        include_hidden=False,
    )

    out = ROOT / "data" / "codex" / "model-catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=== Codex Model Catalog (VERIFIED) ===")
    print(f"Visible models: {len(catalog['models'])}")
    print("")

    for model in catalog["models"]:
        default_marker = " [DEFAULT]" if model["isDefault"] else ""
        print(
            f"{model.get('displayName') or model.get('model')}"
            f" ({model.get('model')}){default_marker}"
        )
        efforts = [
            x["reasoningEffort"]
            for x in model.get("supportedReasoningEfforts") or []
        ]
        print(f"  reasoning: {', '.join(efforts) if efforts else 'none advertised'}")
        print(f"  default:   {model.get('defaultReasoningEffort')}")
        tiers = [x["id"] for x in model.get("serviceTiers") or []]
        if tiers:
            print(f"  tiers:     {', '.join(tiers)}")
        print("")

    print("Attribution capability")
    print(
        "  passive account model attribution: "
        f"{CODEX_CAPABILITIES.passive_model_attribution}"
    )
    print(
        "  managed thread attribution: "
        f"{CODEX_CAPABILITIES.managed_thread_attribution}"
    )
    print("")
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
