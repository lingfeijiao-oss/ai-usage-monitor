from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


class UsageStore:
    """Local aggregate-only storage.

    Never stores prompts, message bodies, source code, email addresses,
    account IDs, OAuth tokens, browser cookies, thread IDs or turn IDs.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def __enter__(self) -> "UsageStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _migrate(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quota_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                limit_id TEXT NOT NULL,
                limit_name TEXT,
                plan_type TEXT,
                window_kind TEXT NOT NULL,
                used_percent REAL,
                remaining_percent REAL,
                window_duration_mins INTEGER,
                resets_at INTEGER,
                ordinary_usage_allowed INTEGER,
                rate_limit_reached_type TEXT,
                provenance TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_quota_samples_time
                ON quota_samples(provider, observed_at);

            CREATE TABLE IF NOT EXISTS token_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                lifetime_tokens INTEGER,
                peak_daily_tokens INTEGER,
                longest_running_turn_sec INTEGER,
                current_streak_days INTEGER,
                longest_streak_days INTEGER,
                provenance TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_token_samples_time
                ON token_samples(provider, observed_at);

            CREATE TABLE IF NOT EXISTS token_daily_buckets (
                provider TEXT NOT NULL,
                start_date TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                provenance TEXT NOT NULL,
                PRIMARY KEY(provider, start_date)
            );

            CREATE TABLE IF NOT EXISTS monitor_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                detail_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS thread_token_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                scope TEXT NOT NULL,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                cache_write_input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_output_tokens INTEGER,
                total_tokens INTEGER,
                cumulative_total_tokens INTEGER,
                model_context_window INTEGER,
                provenance TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_thread_token_events_time
                ON thread_token_events(provider, observed_at);
            """
        )
        self._connection.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._connection.commit()

    def record_snapshot(self, snapshot: dict[str, Any]) -> None:
        observed_at = str(snapshot["observedAt"])
        provider = str(snapshot["provider"])

        quota = snapshot.get("quota") or {}
        quota_provenance = str(quota.get("provenance") or "UNSUPPORTED")
        ordinary_allowed = quota.get("ordinaryUsageAllowed")
        ordinary_int = None if ordinary_allowed is None else int(bool(ordinary_allowed))

        for bucket in quota.get("buckets") or []:
            limit_id = str(bucket.get("limitId") or "unnamed")
            for window_kind in ("primary", "secondary"):
                window = bucket.get(window_kind)
                if not isinstance(window, dict):
                    continue
                self._connection.execute(
                    """
                    INSERT INTO quota_samples(
                        observed_at, provider, limit_id, limit_name, plan_type,
                        window_kind, used_percent, remaining_percent,
                        window_duration_mins, resets_at, ordinary_usage_allowed,
                        rate_limit_reached_type, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observed_at, provider, limit_id, bucket.get("limitName"),
                        bucket.get("planType"), window_kind,
                        window.get("usedPercent"), window.get("remainingPercent"),
                        window.get("windowDurationMins"), window.get("resetsAt"),
                        ordinary_int, bucket.get("rateLimitReachedType"),
                        quota_provenance,
                    ),
                )

        usage = snapshot.get("tokenUsage") or {}
        usage_provenance = str(usage.get("provenance") or "UNSUPPORTED")
        summary = usage.get("summary")
        if isinstance(summary, dict):
            self._connection.execute(
                """
                INSERT INTO token_samples(
                    observed_at, provider, lifetime_tokens, peak_daily_tokens,
                    longest_running_turn_sec, current_streak_days,
                    longest_streak_days, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observed_at, provider, summary.get("lifetimeTokens"),
                    summary.get("peakDailyTokens"),
                    summary.get("longestRunningTurnSec"),
                    summary.get("currentStreakDays"),
                    summary.get("longestStreakDays"),
                    usage_provenance,
                ),
            )

        for row in usage.get("dailyUsageBuckets") or []:
            if not isinstance(row, dict):
                continue
            start_date = row.get("startDate")
            tokens = row.get("tokens")
            if not isinstance(start_date, str) or not isinstance(tokens, int):
                continue
            self._connection.execute(
                """
                INSERT INTO token_daily_buckets(
                    provider, start_date, tokens, observed_at, provenance
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, start_date) DO UPDATE SET
                    tokens=excluded.tokens,
                    observed_at=excluded.observed_at,
                    provenance=excluded.provenance
                """,
                (provider, start_date, tokens, observed_at, usage_provenance),
            )

        self._connection.commit()

    def record_event(
        self,
        observed_at: str,
        provider: str,
        event_kind: str,
        detail: dict[str, Any],
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO monitor_events(observed_at, provider, event_kind, detail_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                observed_at, provider, event_kind,
                json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        self._connection.commit()

    def record_thread_token_event(
        self,
        observed_at: str,
        provider: str,
        event: dict[str, Any],
    ) -> None:
        last = event.get("last") if isinstance(event.get("last"), dict) else {}
        total = event.get("total") if isinstance(event.get("total"), dict) else {}
        self._connection.execute(
            """
            INSERT INTO thread_token_events(
                observed_at, provider, scope, input_tokens,
                cached_input_tokens, cache_write_input_tokens,
                output_tokens, reasoning_output_tokens, total_tokens,
                cumulative_total_tokens, model_context_window, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observed_at,
                provider,
                event.get("scope") or "LOCAL_APP_SERVER_THREAD",
                last.get("inputTokens"),
                last.get("cachedInputTokens"),
                last.get("cacheWriteInputTokens"),
                last.get("outputTokens"),
                last.get("reasoningOutputTokens"),
                last.get("totalTokens"),
                total.get("totalTokens"),
                event.get("modelContextWindow"),
                event.get("provenance") or "VERIFIED",
            ),
        )
        self._connection.commit()

    def latest_quota(self, provider: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT
                q.limit_id, q.limit_name, q.window_kind, q.used_percent,
                q.remaining_percent, q.window_duration_mins, q.resets_at,
                q.ordinary_usage_allowed, q.rate_limit_reached_type,
                q.provenance, q.observed_at
            FROM quota_samples q
            INNER JOIN (
                SELECT limit_id, window_kind, MAX(id) AS max_id
                FROM quota_samples
                WHERE provider = ?
                GROUP BY limit_id, window_kind
            ) x ON q.id = x.max_id
            ORDER BY q.limit_id, q.window_kind
            """,
            (provider,),
        ).fetchall()
        keys = (
            "limitId", "limitName", "windowKind", "usedPercent",
            "remainingPercent", "windowDurationMins", "resetsAt",
            "ordinaryUsageAllowed", "rateLimitReachedType",
            "provenance", "observedAt",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def latest_token_summary(self, provider: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT observed_at, lifetime_tokens, peak_daily_tokens,
                   longest_running_turn_sec, current_streak_days,
                   longest_streak_days, provenance
            FROM token_samples
            WHERE provider = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (provider,),
        ).fetchone()
        if row is None:
            return None
        keys = (
            "observedAt", "lifetimeTokens", "peakDailyTokens",
            "longestRunningTurnSec", "currentStreakDays",
            "longestStreakDays", "provenance",
        )
        return dict(zip(keys, row, strict=True))

    def count_samples(self) -> dict[str, int]:
        quota = self._connection.execute(
            "SELECT COUNT(*) FROM quota_samples"
        ).fetchone()[0]
        token = self._connection.execute(
            "SELECT COUNT(*) FROM token_samples"
        ).fetchone()[0]
        thread = self._connection.execute(
            "SELECT COUNT(*) FROM thread_token_events"
        ).fetchone()[0]
        return {"quota": int(quota), "token": int(token), "thread": int(thread)}

    def close(self) -> None:
        self._connection.close()
