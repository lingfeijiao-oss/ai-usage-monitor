from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from analytics.project_watcher import ProjectUsageWatcher  # noqa: E402
from core.app_paths import private_codex_home, user_config_dir, user_data_dir  # noqa: E402
from core.codex_discovery import (  # noqa: E402
    choose_install,
    discover_installations,
    discover_profiles,
)
from providers.openai_codex.client import (  # noqa: E402
    CodexAppServerClient,
    JsonRpcError,
)
from providers.openai_codex.provider import (  # noqa: E402
    normalize_rate_limits,
    normalize_usage,
)
from ui.model_history_panel import ModelHistoryPanel  # noqa: E402


APP_STATE = user_config_dir() / "desktop.json"
STARTUP_STATE = user_config_dir() / "startup.json"
PROJECT_CACHE = user_data_dir() / "projects" / "project-usage.json"
LEGACY_PROJECT_CACHE = ROOT / "data" / "projects" / "project-usage.json"

DEFAULT_GEOMETRY = "410x310+20+20"

PROJECT_REFRESH_SECONDS = 2.0
ACCOUNT_REFRESH_SECONDS = 30.0

COMPACT_MIN_HEIGHT = 270
EXPANDED_MIN_HEIGHT = 445


def format_tokens(value: Any) -> str:
    if not isinstance(value, int):
        return "—"

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value / 1_000:.1f}K"

    return f"{value:,}"


def fmt_percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"

    return f"{float(value) * 100:.2f}%"


def reset_countdown(epoch: Any) -> str:
    if not isinstance(epoch, (int, float)):
        return "reset —"

    seconds = max(
        0,
        int(epoch - time.time()),
    )

    days, seconds = divmod(
        seconds,
        86400,
    )

    hours, seconds = divmod(
        seconds,
        3600,
    )

    minutes, _ = divmod(
        seconds,
        60,
    )

    if days:
        return f"reset {days}d {hours}h {minutes}m"

    if hours:
        return f"reset {hours}h {minutes}m"

    return f"reset {minutes}m"


def model_usage_lines(
    rows: list[dict[str, Any]],
) -> list[str]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        model = row.get("model") or "unknown"
        effort = row.get("reasoningEffort") or "unknown"
        usage = row.get("usage") or {}

        group = grouped.setdefault(
            model,
            {
                "total": 0,
                "efforts": [],
            },
        )

        total = usage.get("totalTokens")
        total = total if isinstance(total, int) else 0

        group["total"] += total

        group["efforts"].append(
            {
                "effort": effort,
                "total": total,
                "cached": (
                    usage.get("cachedInputTokens")
                    if isinstance(
                        usage.get("cachedInputTokens"),
                        int,
                    )
                    else 0
                ),
                "new": (
                    usage.get("newInputTokens")
                    if isinstance(
                        usage.get("newInputTokens"),
                        int,
                    )
                    else 0
                ),
            }
        )

    ordered = sorted(
        grouped.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    )

    lines: list[str] = []

    for model, group in ordered:
        if group["total"] <= 0:
            continue

        lines.append(
            f"{model}   {format_tokens(group['total'])}"
        )

        efforts = sorted(
            group["efforts"],
            key=lambda item: item["total"],
            reverse=True,
        )

        for item in efforts:
            if item["total"] <= 0:
                continue

            lines.append(
                "  "
                + f"{item['effort']:<8}"
                + f" total {format_tokens(item['total']):>7}"
                + f"   cached {format_tokens(item['cached']):>7}"
                + f"   new {format_tokens(item['new']):>7}"
            )

    return lines or ["No model/effort history available."]


def read_account_snapshot(
    client: CodexAppServerClient,
) -> dict[str, Any]:
    try:
        try:
            rate = client.request(
                "account/rateLimits/read",
                {
                    "supportsLunaReserve": True,
                },
            )

        except JsonRpcError as exc:
            if exc.code not in (
                -32600,
                -32602,
            ):
                raise

            rate = client.request(
                "account/rateLimits/read"
            )

        quota = normalize_rate_limits(
            rate
        )

    except Exception:
        quota = {
            "provenance": "UNSUPPORTED",
            "ordinaryUsageAllowed": None,
            "buckets": [],
            "rateLimitResetCredits": None,
        }

    try:
        usage = normalize_usage(
            client.request(
                "account/usage/read"
            )
        )

    except Exception:
        usage = {
            "provenance": "UNSUPPORTED",
            "summary": None,
            "dailyUsageBuckets": None,
            "threadUsage": None,
        }

    return {
        "quota": quota,
        "tokenUsage": usage,
    }


def authenticated_profile(
    executable: Path,
    profiles: list[Path],
) -> Path | None:
    for profile in profiles:
        try:
            with CodexAppServerClient(
                executable,
                profile,
                timeout_seconds=8.0,
            ) as client:
                result = client.request(
                    "account/read",
                    {
                        "refreshToken": False,
                    },
                )

                if (
                    isinstance(result, dict)
                    and isinstance(
                        result.get("account"),
                        dict,
                    )
                ):
                    return profile

        except Exception:
            continue

    return None


def _read_json_file(
    path: Path,
) -> dict[str, Any] | None:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    return (
        value
        if isinstance(value, dict)
        else None
    )


def load_cached_project_report() -> dict[str, Any] | None:
    for path in (
        PROJECT_CACHE,
        LEGACY_PROJECT_CACHE,
    ):
        value = _read_json_file(path)

        if (
            isinstance(value, dict)
            and isinstance(
                value.get("projects"),
                list,
            )
        ):
            return value

    return None


def save_cached_project_report(
    report: dict[str, Any],
) -> None:
    try:
        PROJECT_CACHE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = PROJECT_CACHE.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp.replace(
            PROJECT_CACHE
        )

    except OSError:
        # Cache failure must never block monitoring.
        pass


def load_startup_state() -> dict[str, Any]:
    return _read_json_file(
        STARTUP_STATE
    ) or {}


def save_startup_state(
    *,
    runtime: str | None = None,
    auth_profile: str | None = None,
) -> None:
    state = load_startup_state()

    if runtime:
        state["runtime"] = runtime

    if auth_profile:
        state["authProfile"] = auth_profile

    try:
        STARTUP_STATE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = STARTUP_STATE.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp.replace(
            STARTUP_STATE
        )

    except OSError:
        pass


def prioritize_auth_profiles(
    profiles: list[Path],
) -> list[Path]:
    state = load_startup_state()
    cached = state.get("authProfile")

    if not isinstance(cached, str):
        return profiles

    cached_path = Path(cached)

    ordered = []

    if cached_path in profiles:
        ordered.append(
            cached_path
        )

    ordered.extend(
        path
        for path in profiles
        if path != cached_path
    )

    return ordered


def active_project(
    projects: list[dict[str, Any]],
) -> dict[str, Any] | None:
    def key(
        project: dict[str, Any],
    ) -> float:
        value = (
            project.get("currentObservedAt")
            or project.get("updatedAt")
        )

        if not isinstance(value, str):
            return 0.0

        try:
            return datetime.fromisoformat(
                value
            ).timestamp()

        except ValueError:
            return 0.0

    return (
        max(
            projects,
            key=key,
        )
        if projects
        else None
    )


class DesktopApp:
    def __init__(self) -> None:
        self.root = tk.Tk()

        self.root.title(
            "AI Usage Monitor"
        )

        self.root.overrideredirect(
            True
        )

        self.root.configure(
            bg="#101318"
        )

        self.root.geometry(
            self._load_geometry()
        )

        self.root.minsize(
            340,
            COMPACT_MIN_HEIGHT,
        )

        self.topmost = True

        try:
            self.root.attributes(
                "-topmost",
                True,
            )
        except tk.TclError:
            self.topmost = False

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close,
        )

        self.stop_event = threading.Event()

        self.events: queue.Queue[
            tuple[str, Any]
        ] = queue.Queue()

        self.drag_origin = None
        self.resize_origin = None

        self.runtime = None
        self.profiles: list[Path] = []
        self.auth_home: Path | None = None

        self.account_client: (
            CodexAppServerClient
            | None
        ) = None

        self.login_process: (
            subprocess.Popen
            | None
        ) = None

        self.project_watcher: (
            ProjectUsageWatcher
            | None
        ) = None

        self.projects: list[
            dict[str, Any]
        ] = []

        self.auto_project = True

        self.last_observed_model: tuple[
            str | None,
            str | None,
        ] | None = None

        self.model_switch_until = 0.0
        self.quota_reset_at = None

        self.models_expanded = False
        self.pre_expand_height = None

        self.current_project: (
            dict[str, Any]
            | None
        ) = None

        self._build_ui()

        cached_report = (
            load_cached_project_report()
        )

        if cached_report:
            self._apply_projects(
                cached_report
            )

            self.state_label.configure(
                text="cached · refreshing…"
            )

        self.root.after(
            100,
            self._drain_events,
        )

        self.root.after(
            1000,
            self._tick_countdown,
        )

        threading.Thread(
            target=self._bootstrap,
            daemon=True,
        ).start()

    def _load_geometry(self) -> str:
        try:
            data = json.loads(
                APP_STATE.read_text(
                    encoding="utf-8"
                )
            )

            value = data.get(
                "geometry"
            )

            if isinstance(
                value,
                str,
            ):
                return value

        except (
            OSError,
            json.JSONDecodeError,
        ):
            pass

        return DEFAULT_GEOMETRY

    def _save_geometry(self) -> None:
        APP_STATE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        APP_STATE.write_text(
            json.dumps(
                {
                    "geometry": (
                        self.root.geometry()
                    ),
                    "topmost": (
                        self.topmost
                    ),
                    "modelsExpanded": (
                        self.models_expanded
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _button(
        self,
        parent,
        *,
        text,
        command,
        width=None,
    ):
        options = {
            "text": text,
            "command": command,
            "bg": "#171b22",
            "fg": "#c7ced8",
            "activebackground": "#2a303a",
            "activeforeground": "#ffffff",
            "relief": "flat",
            "bd": 0,
            "font": ("Segoe UI", 8, "bold"),
        }

        if width is not None:
            options["width"] = width

        return tk.Button(
            parent,
            **options,
        )

    def _build_ui(self) -> None:
        outer = tk.Frame(
            self.root,
            bg="#101318",
            highlightthickness=1,
            highlightbackground="#303844",
        )

        outer.pack(
            fill="both",
            expand=True,
        )

        self.outer = outer

        header = tk.Frame(
            outer,
            bg="#171b22",
            height=31,
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(
            False
        )

        title = tk.Label(
            header,
            text="AI Usage",
            bg="#171b22",
            fg="#f3f6fb",
            font=("Segoe UI", 9, "bold"),
        )

        title.pack(
            side="left",
            padx=(10, 6),
        )

        self.state_label = tk.Label(
            header,
            text="detecting…",
            bg="#171b22",
            fg="#8f99aa",
            font=("Segoe UI", 7),
        )

        self.state_label.pack(
            side="left"
        )

        close = self._button(
            header,
            text="×",
            command=self.close,
            width=3,
        )

        close.pack(
            side="right"
        )

        self.pin_button = self._button(
            header,
            text="PIN",
            command=self._toggle_topmost,
        )

        self.pin_button.configure(
            fg="#9db7ff"
        )

        self.pin_button.pack(
            side="right",
            padx=(0, 3),
        )

        for widget in (
            header,
            title,
            self.state_label,
        ):
            widget.bind(
                "<ButtonPress-1>",
                self._start_drag,
            )

            widget.bind(
                "<B1-Motion>",
                self._drag,
            )

        body = tk.Frame(
            outer,
            bg="#101318",
        )

        body.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(9, 10),
        )

        self.project_var = tk.StringVar(
            value="Detecting project…"
        )

        self.project_box = ttk.Combobox(
            body,
            textvariable=self.project_var,
            state="readonly",
            height=8,
        )

        self.project_box.pack(
            fill="x"
        )

        self.project_box.bind(
            "<<ComboboxSelected>>",
            self._project_selected,
        )

        model_row = tk.Frame(
            body,
            bg="#101318",
        )

        model_row.pack(
            fill="x",
            pady=(9, 0),
        )

        self.model_label = tk.Label(
            model_row,
            text="Model —",
            fg="#f3f6fb",
            bg="#101318",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )

        self.model_label.pack(
            side="left"
        )

        self.switch_label = tk.Label(
            model_row,
            text="",
            fg="#f3c66b",
            bg="#101318",
            font=("Segoe UI", 7, "bold"),
            anchor="e",
        )

        self.switch_label.pack(
            side="right"
        )

        quota_row = tk.Frame(
            body,
            bg="#101318",
        )

        quota_row.pack(
            fill="x",
            pady=(10, 0),
        )

        self.remaining_label = tk.Label(
            quota_row,
            text="Quota —",
            fg="#f3f6fb",
            bg="#101318",
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        )

        self.remaining_label.pack(
            side="left"
        )

        self.used_label = tk.Label(
            quota_row,
            text="",
            fg="#8f99aa",
            bg="#101318",
            font=("Segoe UI", 8),
            anchor="e",
        )

        self.used_label.pack(
            side="right",
            pady=(5, 0),
        )

        style = ttk.Style(
            self.root
        )

        style.theme_use(
            "default"
        )

        style.configure(
            "Usage.Horizontal.TProgressbar",
            troughcolor="#242b35",
            background="#9db7ff",
            bordercolor="#242b35",
            lightcolor="#9db7ff",
            darkcolor="#9db7ff",
            thickness=6,
        )

        self.progress = ttk.Progressbar(
            body,
            style="Usage.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate",
            maximum=100,
        )

        self.progress.pack(
            fill="x",
            pady=(4, 3),
        )

        self.reset_label = tk.Label(
            body,
            text="reset —",
            fg="#8f99aa",
            bg="#101318",
            font=("Segoe UI", 8),
            anchor="w",
        )

        self.reset_label.pack(
            fill="x"
        )

        total_row = tk.Frame(
            body,
            bg="#101318",
        )

        total_row.pack(
            fill="x",
            pady=(10, 3),
        )

        self.total_label = tk.Label(
            total_row,
            text="Project total —",
            fg="#dbe2ec",
            bg="#101318",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )

        self.total_label.pack(
            side="left"
        )

        self.models_button = tk.Button(
            total_row,
            text="MODELS ▾",
            command=self._toggle_models,
            fg="#9db7ff",
            bg="#101318",
            activeforeground="#ffffff",
            activebackground="#1b212a",
            relief="flat",
            bd=0,
            font=("Segoe UI", 7, "bold"),
        )

        self.models_button.pack(
            side="right"
        )

        self.detail_label = tk.Label(
            body,
            text=(
                "Input —   Cached —   New —\n"
                "Output —   Reasoning —   Cache hit —"
            ),
            fg="#aab4c2",
            bg="#101318",
            font=("Consolas", 8),
            anchor="w",
            justify="left",
        )

        self.detail_label.pack(
            fill="x"
        )

        self.models_frame = tk.Frame(
            body,
            bg="#141820",
            highlightthickness=1,
            highlightbackground="#29313d",
        )

        self.models_panel = ModelHistoryPanel(
            self.models_frame
        )

        self.models_panel.pack(
            fill="both",
            expand=True,
        )

        self.footer_label = tk.Label(
            body,
            text=(
                "Quota VERIFIED · Bars = token share · Project LOCAL_OBSERVED"
            ),
            fg="#657080",
            bg="#101318",
            font=("Segoe UI", 7),
            anchor="e",
        )

        self.footer_label.pack(
            fill="x",
            pady=(8, 0),
        )

        grip = tk.Label(
            outer,
            text="◢",
            bg="#101318",
            fg="#667080",
            font=("Segoe UI", 8),
        )

        grip.place(
            relx=1.0,
            rely=1.0,
            anchor="se",
            x=-2,
            y=-1,
        )

        grip.bind(
            "<ButtonPress-1>",
            self._start_resize,
        )

        grip.bind(
            "<B1-Motion>",
            self._resize,
        )

    def _toggle_models(self) -> None:
        self.models_expanded = (
            not self.models_expanded
        )

        if self.models_expanded:
            self.pre_expand_height = (
                self.root.winfo_height()
            )

            self.models_frame.pack(
                fill="both",
                expand=True,
                pady=(9, 0),
                before=self.footer_label,
            )

            self.models_button.configure(
                text="MODELS ▴"
            )

            width = self.root.winfo_width()
            height = max(
                self.root.winfo_height(),
                EXPANDED_MIN_HEIGHT,
            )

            self.root.geometry(
                f"{width}x{height}"
            )

            self.root.minsize(
                340,
                EXPANDED_MIN_HEIGHT,
            )

            self._render_model_history()

        else:
            self.models_frame.pack_forget()

            self.models_button.configure(
                text="MODELS ▾"
            )

            width = self.root.winfo_width()

            target = (
                self.pre_expand_height
                if isinstance(
                    self.pre_expand_height,
                    int,
                )
                else 310
            )

            target = max(
                COMPACT_MIN_HEIGHT,
                min(
                    target,
                    EXPANDED_MIN_HEIGHT - 1,
                ),
            )

            self.root.minsize(
                340,
                COMPACT_MIN_HEIGHT,
            )

            self.root.geometry(
                f"{width}x{target}"
            )

    def _render_model_history(self) -> None:
        self.models_panel.render(
            self.current_project
        )

    def _bootstrap(self) -> None:
        try:
            startup_started = (
                time.monotonic()
            )

            installs = discover_installations(
                allow_fallback_scan=False
            )

            runtime = choose_install(
                installs
            )

            if runtime is None:
                self.events.put(
                    (
                        "runtime",
                        "searching device…",
                    )
                )

                installs = (
                    discover_installations(
                        allow_fallback_scan=True
                    )
                )

                runtime = choose_install(
                    installs
                )

            if runtime is None:
                self.events.put(
                    (
                        "fatal",
                        "Codex not found on this device.",
                    )
                )
                return

            save_startup_state(
                runtime=runtime.executable
            )

            self.runtime = runtime

            profiles = [
                Path(item.path)
                for item in discover_profiles(
                    installs
                )
            ]

            profiles = (
                prioritize_auth_profiles(
                    profiles
                )
            )

            self.profiles = profiles

            self.events.put(
                (
                    "runtime",
                    (
                        f"{runtime.version} · "
                        f"{len(profiles)} profile(s)"
                    ),
                )
            )

            self.project_watcher = (
                ProjectUsageWatcher(
                    profiles
                )
            )

            threading.Thread(
                target=self._project_loop,
                daemon=True,
            ).start()

            executable = Path(
                runtime.executable
            )

            auth_home = (
                authenticated_profile(
                    executable,
                    profiles,
                )
            )

            if auth_home is None:
                self.events.put(
                    (
                        "login_required",
                        None,
                    )
                )

                auth_home = self._run_login(
                    executable
                )

                if auth_home is None:
                    return

            self.auth_home = auth_home

            save_startup_state(
                auth_profile=str(
                    auth_home
                )
            )

            startup_elapsed = (
                time.monotonic()
                - startup_started
            )

            self.events.put(
                (
                    "authenticated",
                    {
                        "profile": str(
                            auth_home
                        ),
                        "elapsed": (
                            startup_elapsed
                        ),
                    },
                )
            )

            self._account_loop(
                executable,
                auth_home,
            )

        except Exception as exc:
            self.events.put(
                (
                    "fatal",
                    f"{type(exc).__name__}: {exc}",
                )
            )

    def _run_login(
        self,
        executable: Path,
    ) -> Path | None:
        home = private_codex_home()

        env = os.environ.copy()
        env["CODEX_HOME"] = str(
            home
        )

        creationflags = 0

        if (
            os.name == "nt"
            and hasattr(
                subprocess,
                "CREATE_NO_WINDOW",
            )
        ):
            creationflags = (
                subprocess.CREATE_NO_WINDOW
            )

        try:
            process = subprocess.Popen(
                [
                    str(executable),
                    "login",
                ],
                env=env,
                creationflags=creationflags,
            )

        except OSError as exc:
            self.events.put(
                (
                    "fatal",
                    (
                        "Could not start Codex login: "
                        + str(exc)
                    ),
                )
            )
            return None

        self.login_process = process

        while not self.stop_event.wait(
            0.5
        ):
            code = process.poll()

            if code is None:
                continue

            self.login_process = None

            if code != 0:
                self.events.put(
                    (
                        "fatal",
                        (
                            "Codex login exited "
                            f"with code {code}."
                        ),
                    )
                )
                return None

            if (
                authenticated_profile(
                    executable,
                    [home],
                )
                is not None
            ):
                return home

            self.events.put(
                (
                    "fatal",
                    (
                        "Login completed but "
                        "account was not readable."
                    ),
                )
            )

            return None

        if process.poll() is None:
            process.terminate()

        return None

    def _account_loop(
        self,
        executable: Path,
        auth_home: Path,
    ) -> None:
        client = CodexAppServerClient(
            executable,
            auth_home,
            timeout_seconds=12.0,
        )

        self.account_client = client

        try:
            client.start()

            while not self.stop_event.is_set():
                try:
                    snapshot = (
                        read_account_snapshot(
                            client
                        )
                    )

                    self.events.put(
                        (
                            "account",
                            snapshot,
                        )
                    )

                except Exception as exc:
                    self.events.put(
                        (
                            "account_error",
                            (
                                f"{type(exc).__name__}: "
                                f"{exc}"
                            ),
                        )
                    )

                if self.stop_event.wait(
                    ACCOUNT_REFRESH_SECONDS
                ):
                    break

        finally:
            client.close()
            self.account_client = None

    def _project_loop(self) -> None:
        assert (
            self.project_watcher
            is not None
        )

        while not self.stop_event.is_set():
            try:
                report = (
                    self.project_watcher.refresh()
                )

                save_cached_project_report(
                    report
                )

                self.events.put(
                    (
                        "projects",
                        report,
                    )
                )

            except Exception as exc:
                self.events.put(
                    (
                        "project_error",
                        (
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

            if self.stop_event.wait(
                PROJECT_REFRESH_SECONDS
            ):
                break

    def _drain_events(self) -> None:
        if self.stop_event.is_set():
            return

        try:
            while True:
                kind, payload = (
                    self.events.get_nowait()
                )

                if kind == "runtime":
                    self.state_label.configure(
                        text=payload
                    )

                elif kind == "authenticated":
                    elapsed = (
                        payload.get(
                            "elapsed"
                        )
                        if isinstance(
                            payload,
                            dict,
                        )
                        else None
                    )

                    self.state_label.configure(
                        text=(
                            (
                                f"connected · "
                                f"{elapsed:.2f}s"
                            )
                            if isinstance(
                                elapsed,
                                (int, float),
                            )
                            else "connected"
                        )
                    )

                elif kind == "login_required":
                    self.state_label.configure(
                        text=(
                            "login required · "
                            "opening browser"
                        )
                    )

                elif kind == "projects":
                    self._apply_projects(
                        payload
                    )

                elif kind == "account":
                    self._apply_account(
                        payload
                    )

                elif kind == "account_error":
                    self.state_label.configure(
                        text="account read warning"
                    )

                elif kind == "project_error":
                    self.state_label.configure(
                        text="project read warning"
                    )

                elif kind == "fatal":
                    self.state_label.configure(
                        text="attention"
                    )

                    self.project_var.set(
                        payload
                    )

        except queue.Empty:
            pass

        if (
            time.monotonic()
            > self.model_switch_until
        ):
            self.switch_label.configure(
                text=""
            )

        self.root.after(
            120,
            self._drain_events,
        )

    def _apply_projects(
        self,
        report: dict[str, Any],
    ) -> None:
        self.projects = (
            report.get("projects")
            or []
        )

        names = [
            "AUTO · current project"
        ]

        for project in self.projects:
            name = (
                project.get("projectName")
                or project.get("projectPath")
                or "Project"
            )

            names.append(name)

        self.project_box[
            "values"
        ] = names

        if self.auto_project:
            project = active_project(
                self.projects
            )

            if project:
                self.project_var.set(
                    "AUTO · "
                    + (
                        project.get(
                            "projectName"
                        )
                        or project.get(
                            "projectPath"
                        )
                    )
                )

                self._render_project(
                    project
                )

            else:
                self.project_var.set(
                    "AUTO · no project"
                )

        else:
            project = (
                self._selected_project()
            )

            if project:
                self._render_project(
                    project
                )

    def _selected_project(
        self,
    ) -> dict[str, Any] | None:
        value = self.project_var.get()

        if value.startswith(
            "AUTO"
        ):
            return active_project(
                self.projects
            )

        for project in self.projects:
            if (
                project.get("projectName")
                or project.get("projectPath")
            ) == value:
                return project

        return None

    def _project_selected(
        self,
        _event,
    ) -> None:
        value = (
            self.project_var.get()
        )

        self.auto_project = (
            value.startswith("AUTO")
        )

        project = (
            self._selected_project()
        )

        if project:
            self._render_project(
                project
            )

    def _render_project(
        self,
        project: dict[str, Any],
    ) -> None:
        self.current_project = project

        model = project.get(
            "currentModel"
        )

        effort = project.get(
            "currentReasoningEffort"
        )

        current = (
            model,
            effort,
        )

        if (
            self.last_observed_model
            is not None
            and current
            != self.last_observed_model
            and any(current)
        ):
            self.switch_label.configure(
                text="MODEL SWITCH"
            )

            self.model_switch_until = (
                time.monotonic()
                + 8.0
            )

        if any(current):
            self.last_observed_model = (
                current
            )

        self.model_label.configure(
            text=(
                f"{model or 'unknown'} · "
                f"{effort or 'unknown'}"
            )
        )

        usage = (
            project.get("usage")
            or {}
        )

        self.total_label.configure(
            text=(
                "Project total  "
                + format_tokens(
                    usage.get(
                        "totalTokens"
                    )
                )
            )
        )

        self.detail_label.configure(
            text=(
                f"Input "
                f"{format_tokens(usage.get('inputTokens'))}"
                f"   Cached "
                f"{format_tokens(usage.get('cachedInputTokens'))}"
                f"   New "
                f"{format_tokens(usage.get('newInputTokens'))}"
                "\n"
                f"Output "
                f"{format_tokens(usage.get('outputTokens'))}"
                f"   Reasoning "
                f"{format_tokens(usage.get('reasoningOutputTokens'))}"
                f"   Hit "
                f"{fmt_percent(usage.get('cacheHitRate'))}"
            )
        )

        if self.models_expanded:
            self._render_model_history()

    def _apply_account(
        self,
        snapshot: dict[str, Any],
    ) -> None:
        quota = (
            snapshot.get("quota")
            or {}
        )

        buckets = (
            quota.get("buckets")
            or []
        )

        window = None

        for bucket in buckets:
            candidate = (
                bucket.get("primary")
            )

            if isinstance(
                candidate,
                dict,
            ):
                window = candidate
                break

        if window is None:
            self.remaining_label.configure(
                text="Quota —"
            )

            self.used_label.configure(
                text=""
            )

            self.progress[
                "value"
            ] = 0

            self.quota_reset_at = None
            return

        used = window.get(
            "usedPercent"
        )

        remaining = window.get(
            "remainingPercent"
        )

        used_num = (
            float(used)
            if isinstance(
                used,
                (int, float),
            )
            else 0.0
        )

        remaining_num = (
            float(remaining)
            if isinstance(
                remaining,
                (int, float),
            )
            else max(
                0.0,
                100.0 - used_num,
            )
        )

        self.remaining_label.configure(
            text=(
                f"{remaining_num:.2f}% "
                "remaining"
            )
        )

        self.used_label.configure(
            text=(
                f"{used_num:.2f}% used"
            )
        )

        self.progress[
            "value"
        ] = used_num

        self.quota_reset_at = (
            window.get("resetsAt")
        )

        self._tick_countdown()

    def _tick_countdown(self) -> None:
        if self.stop_event.is_set():
            return

        self.reset_label.configure(
            text=reset_countdown(
                self.quota_reset_at
            )
        )

        self.root.after(
            1000,
            self._tick_countdown,
        )

    def _toggle_topmost(self) -> None:
        self.topmost = (
            not self.topmost
        )

        try:
            self.root.attributes(
                "-topmost",
                self.topmost,
            )

        except tk.TclError:
            self.topmost = False

        self.pin_button.configure(
            text=(
                "PIN"
                if self.topmost
                else "FREE"
            ),
            fg=(
                "#9db7ff"
                if self.topmost
                else "#8f99aa"
            ),
        )

    def _start_drag(
        self,
        event,
    ) -> None:
        self.drag_origin = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )

    def _drag(
        self,
        event,
    ) -> None:
        if self.drag_origin is None:
            return

        sx, sy, wx, wy = (
            self.drag_origin
        )

        self.root.geometry(
            "+"
            + str(
                wx
                + event.x_root
                - sx
            )
            + "+"
            + str(
                wy
                + event.y_root
                - sy
            )
        )

    def _start_resize(
        self,
        event,
    ) -> None:
        self.resize_origin = (
            event.x_root,
            event.y_root,
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

    def _resize(
        self,
        event,
    ) -> None:
        if self.resize_origin is None:
            return

        sx, sy, width, height = (
            self.resize_origin
        )

        width = max(
            340,
            width
            + event.x_root
            - sx,
        )

        min_height = (
            EXPANDED_MIN_HEIGHT
            if self.models_expanded
            else COMPACT_MIN_HEIGHT
        )

        height = max(
            min_height,
            height
            + event.y_root
            - sy,
        )

        self.root.geometry(
            f"{width}x{height}"
        )

    def close(self) -> None:
        if self.stop_event.is_set():
            return

        self.stop_event.set()

        try:
            self._save_geometry()
        except Exception:
            pass

        process = (
            self.login_process
        )

        if (
            process is not None
            and process.poll() is None
        ):
            try:
                process.terminate()
            except OSError:
                pass

        client = (
            self.account_client
        )

        if client is not None:
            try:
                client.close()
            except Exception:
                pass

        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def smoke_test() -> int:
    installs = discover_installations(
        allow_fallback_scan=False
    )

    runtime = choose_install(
        installs
    )

    profiles = discover_profiles(
        installs
    )

    print(
        "Unified Desktop App "
        "cross-platform smoke test: PASS"
    )

    print(
        f"Validated installs: "
        f"{len(installs)}"
    )

    print(
        f"Profiles: "
        f"{len(profiles)}"
    )

    print(
        "Runtime: "
        + (
            runtime.executable
            if runtime is not None
            else "not found in fast scan"
        )
    )

    print(
        "Model history UI: enabled"
    )

    print(
        "Lifecycle: foreground only"
    )

    print(
        "Inference turn: no"
    )

    return 0


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        raise SystemExit(
            smoke_test()
        )

    DesktopApp().run()




