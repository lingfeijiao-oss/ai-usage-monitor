from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from managed import (  # noqa: E402
    ManagedRunError,
    ManagedRunSpec,
    build_dry_run_plan,
    quota_allows_managed_run,
)
from providers.openai_codex import CodexProvider  # noqa: E402
from providers.openai_codex.client import CodexAppServerClient  # noqa: E402
from providers.openai_codex.event_normalizer import normalize_thread_token_event  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def extract_id(result, key):
    if not isinstance(result, dict):
        raise ManagedRunError(f"{key} response was not an object")
    obj = result.get(key)
    if not isinstance(obj, dict):
        raise ManagedRunError(f"{key} response did not include {key}")
    value = obj.get("id")
    if not isinstance(value, str) or not value:
        raise ManagedRunError(f"{key} response did not contain an id")
    return value


def event_matches_turn(params, thread_id, turn_id):
    if not isinstance(params, dict):
        return False

    event_thread = params.get("threadId")
    if isinstance(event_thread, str) and event_thread != thread_id:
        return False

    direct_turn = params.get("turnId")
    if isinstance(direct_turn, str):
        return direct_turn == turn_id

    turn = params.get("turn")
    if isinstance(turn, dict) and isinstance(turn.get("id"), str):
        return turn["id"] == turn_id

    # Dedicated app-server connection owns only this managed run. If a completion
    # notification has no explicit turn id, accept it as the active turn.
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Codex managed-thread measurement runner"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--prompt", default="Reply with exactly: OK")
    parser.add_argument("--cwd", default=str(ROOT))
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write"),
        default="read-only",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually start a Codex inference turn. Without this flag, dry-run only.",
    )
    args = parser.parse_args()

    catalog = load_json(ROOT / "data" / "codex" / "model-catalog.json")
    spec = ManagedRunSpec(
        model=args.model,
        reasoning_effort=args.effort,
        prompt=args.prompt,
        cwd=args.cwd,
        sandbox=args.sandbox,
        timeout_seconds=args.timeout,
    )

    try:
        plan = build_dry_run_plan(catalog, spec)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    print("=== Managed Codex task ===")
    print(f"Model:    {plan['selection']['displayName'] or spec.model}")
    print(f"Effort:   {spec.reasoning_effort}")
    print(f"Sandbox:  {spec.sandbox}")
    print(f"CWD:      {spec.cwd}")
    print(f"Prompt:   {len(spec.prompt)} characters (content not persisted)")
    print("Mode:     MANAGED_THREAD")
    print("")

    if not args.execute:
        print("DRY RUN: PASS")
        print("No thread or inference turn was started.")
        return 0

    cfg = load_json(ROOT / "config" / "local.codex.json")
    provider = CodexProvider(
        Path(cfg["executable"]),
        Path(cfg["codex_home"]),
        codex_version=cfg.get("codex_version"),
    )

    start_snapshot = provider.read_snapshot()
    allowed, reason = quota_allows_managed_run(start_snapshot)
    if not allowed:
        print(f"BLOCKED BEFORE INFERENCE: {reason}")
        print("No managed thread/turn was started.")
        return 3

    run_id = uuid.uuid4().hex[:16]
    started_at = utc_now()
    started_mono = time.monotonic()

    thread_id = None
    turn_id = None
    latest_token_event = None
    completion_status = None

    try:
        with CodexAppServerClient(
            Path(cfg["executable"]),
            Path(cfg["codex_home"]),
            timeout_seconds=max(15.0, min(spec.timeout_seconds, 60.0)),
        ) as client:
            thread_result = client.request(
                "thread/start",
                {
                    "model": spec.model,
                    "cwd": spec.cwd,
                    "sandbox": spec.sandbox,
                    "ephemeral": True,
                },
            )
            thread_id = extract_id(thread_result, "thread")

            turn_result = client.request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [
                        {
                            "type": "text",
                            "text": spec.prompt,
                            "textElements": [],
                        }
                    ],
                    "model": spec.model,
                    "effort": spec.reasoning_effort,
                },
            )
            turn_id = extract_id(turn_result, "turn")

            deadline = time.monotonic() + spec.timeout_seconds
            while time.monotonic() < deadline:
                event = client.next_notification(timeout=1.0)
                if not event:
                    continue

                method = event.get("method")
                params = event.get("params")

                if method == "thread/tokenUsage/updated":
                    if event_matches_turn(params, thread_id, turn_id):
                        normalized = normalize_thread_token_event(params)
                        if normalized is not None:
                            latest_token_event = normalized
                    continue

                if method == "turn/completed" and event_matches_turn(
                    params, thread_id, turn_id
                ):
                    turn = params.get("turn") if isinstance(params, dict) else None
                    if isinstance(turn, dict):
                        completion_status = turn.get("status")
                    else:
                        completion_status = "completed"
                    break

                if method == "error":
                    raise ManagedRunError("Codex emitted an error notification")

            else:
                try:
                    client.request(
                        "turn/interrupt",
                        {"threadId": thread_id, "turnId": turn_id},
                    )
                except Exception:
                    pass
                raise ManagedRunError(
                    f"Managed turn timed out after {spec.timeout_seconds:.1f}s"
                )

            try:
                client.request("thread/unsubscribe", {"threadId": thread_id})
            except Exception:
                pass

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 4

    ended_at = utc_now()
    elapsed = time.monotonic() - started_mono
    end_snapshot = provider.read_snapshot()

    # Only hashed IDs are persisted, never raw thread/turn IDs.
    record = {
        "schemaVersion": 1,
        "runId": run_id,
        "provider": "openai_codex",
        "mode": "MANAGED_THREAD",
        "attributionProvenance": "VERIFIED",
        "startedAt": started_at,
        "endedAt": ended_at,
        "elapsedSeconds": elapsed,
        "model": spec.model,
        "reasoningEffort": spec.reasoning_effort,
        "sandbox": spec.sandbox,
        "cwdRecorded": False,
        "promptRecorded": False,
        "promptCharacterCount": len(spec.prompt),
        "threadIdHash": digest_id(thread_id),
        "turnIdHash": digest_id(turn_id),
        "completionStatus": completion_status,
        "threadTokenUsage": latest_token_event,
        "startQuota": start_snapshot.get("quota"),
        "endQuota": end_snapshot.get("quota"),
        "startLifetimeTokens": (
            (start_snapshot.get("tokenUsage") or {})
            .get("summary", {})
            .get("lifetimeTokens")
        ),
        "endLifetimeTokens": (
            (end_snapshot.get("tokenUsage") or {})
            .get("summary", {})
            .get("lifetimeTokens")
        ),
    }

    out = ROOT / "data" / "managed-runs" / f"{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("MANAGED RUN COMPLETE")
    print(f"Run:      {run_id}")
    print(f"Elapsed:  {elapsed:.1f}s")
    print(f"Status:   {completion_status}")
    if latest_token_event:
        last = latest_token_event.get("last") or {}
        total = latest_token_event.get("total") or {}
        print("Thread token usage [VERIFIED]")
        print(f"  last input:      {last.get('inputTokens')}")
        print(f"  last cached:     {last.get('cachedInputTokens')}")
        print(f"  last output:     {last.get('outputTokens')}")
        print(f"  last reasoning:  {last.get('reasoningOutputTokens')}")
        print(f"  last total:      {last.get('totalTokens')}")
        print(f"  thread total:    {total.get('totalTokens')}")
    else:
        print("Thread token event: not observed")

    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
