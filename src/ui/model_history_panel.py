from __future__ import annotations

import tkinter as tk
from typing import Any

BG = "#141820"
ROW_BG = "#171c24"
CURRENT_BG = "#1c2635"
EFFORT_BG = "#151a21"
TEXT = "#e6ebf2"
MUTED = "#8f99aa"
CURRENT_TEXT = "#ffffff"
BAR_TRACK = "#28303b"
MODEL_BAR = "#748dbd"
CURRENT_BAR = "#9db7ff"
EFFORT_BAR = "#71809a"
BORDER = "#29313d"


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


def percent_of(part: Any, whole: Any) -> float:
    if not isinstance(part, (int, float)):
        return 0.0
    if not isinstance(whole, (int, float)) or whole <= 0:
        return 0.0
    return max(0.0, (float(part) / float(whole)) * 100.0)


def _int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def build_model_usage_view(
    rows: list[dict[str, Any]],
    project_total: int,
    *,
    current_model: str | None = None,
    current_effort: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        model = row.get("model") or "unknown"
        effort = row.get("reasoningEffort") or "unknown"
        usage = row.get("usage") or {}

        total = _int(usage.get("totalTokens"))
        input_tokens = _int(usage.get("inputTokens"))
        cached = _int(usage.get("cachedInputTokens"))
        new_input = _int(usage.get("newInputTokens"))

        group = grouped.setdefault(
            model,
            {
                "model": model,
                "totalTokens": 0,
                "inputTokens": 0,
                "cachedInputTokens": 0,
                "newInputTokens": 0,
                "efforts": [],
            },
        )

        group["totalTokens"] += total
        group["inputTokens"] += input_tokens
        group["cachedInputTokens"] += cached
        group["newInputTokens"] += new_input
        group["efforts"].append(
            {
                "effort": effort,
                "totalTokens": total,
                "inputTokens": input_tokens,
                "cachedInputTokens": cached,
                "newInputTokens": new_input,
            }
        )

    output: list[dict[str, Any]] = []

    for group in grouped.values():
        model_total = group["totalTokens"]
        if model_total <= 0:
            continue

        efforts = []
        for effort in group["efforts"]:
            effort_total = effort["totalTokens"]
            if effort_total <= 0:
                continue

            effort_input = effort["inputTokens"]
            effort_cached = effort["cachedInputTokens"]
            effort_new = effort["newInputTokens"]

            efforts.append(
                {
                    **effort,
                    "projectSharePercent": percent_of(effort_total, project_total),
                    "modelSharePercent": percent_of(effort_total, model_total),
                    "cachedInputPercent": percent_of(effort_cached, effort_input),
                    "newInputPercent": percent_of(effort_new, effort_input),
                    "isCurrent": (
                        group["model"] == current_model
                        and effort["effort"] == current_effort
                    ),
                }
            )

        efforts.sort(key=lambda item: item["totalTokens"], reverse=True)

        model_input = group["inputTokens"]
        output.append(
            {
                "model": group["model"],
                "totalTokens": model_total,
                "inputTokens": model_input,
                "cachedInputTokens": group["cachedInputTokens"],
                "newInputTokens": group["newInputTokens"],
                "projectSharePercent": percent_of(model_total, project_total),
                "cachedInputPercent": percent_of(
                    group["cachedInputTokens"], model_input
                ),
                "newInputPercent": percent_of(
                    group["newInputTokens"], model_input
                ),
                "isCurrent": group["model"] == current_model,
                "efforts": efforts,
            }
        )

    output.sort(key=lambda item: item["totalTokens"], reverse=True)
    return output


def model_summary_text(model: dict[str, Any]) -> str:
    return (
        f"{format_tokens(model['totalTokens'])}"
        f" · Project {model['projectSharePercent']:.2f}%"
    )


def effort_summary_text(effort: dict[str, Any]) -> str:
    return (
        f"{format_tokens(effort['totalTokens'])}"
        f" · Model {effort['modelSharePercent']:.2f}%"
    )


def effort_detail_lines(effort: dict[str, Any]) -> tuple[str, str]:
    return (
        f"Project {effort['projectSharePercent']:.2f}%",
        (
            f"Cached {format_tokens(effort['cachedInputTokens'])}"
            f" · {effort['cachedInputPercent']:.2f}%"
            f"    New {format_tokens(effort['newInputTokens'])}"
            f" · {effort['newInputPercent']:.2f}%"
        ),
    )


class RatioBar(tk.Canvas):
    def __init__(self, parent, *, percent: float, fill: str, height: int = 7):
        super().__init__(
            parent,
            height=height,
            bg=BAR_TRACK,
            bd=0,
            highlightthickness=0,
        )
        self.percent = max(0.0, min(100.0, float(percent)))
        self.fill = fill
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        fill_width = int(width * self.percent / 100.0)
        self.create_rectangle(
            0, 0, fill_width, height, fill=self.fill, outline=""
        )


class ModelHistoryPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self.expanded_models: set[str] = set()
        self._initialized = False
        self.current_project: dict[str, Any] | None = None

        self.canvas = tk.Canvas(
            self, bg=BG, highlightthickness=0, bd=0
        )
        self.scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._inner_configure)
        self.canvas.bind("<Configure>", self._canvas_configure)
        self.canvas.bind("<MouseWheel>", self._mousewheel)
        self.canvas.bind(
            "<Button-4>",
            lambda _event: self.canvas.yview_scroll(-1, "units"),
        )
        self.canvas.bind(
            "<Button-5>",
            lambda _event: self.canvas.yview_scroll(1, "units"),
        )

    def _inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _mousewheel(self, event):
        delta = int(-event.delta / 120)
        if delta:
            self.canvas.yview_scroll(delta, "units")

    def _clear(self):
        for child in self.inner.winfo_children():
            child.destroy()

    def _toggle_model(self, model: str):
        if model in self.expanded_models:
            self.expanded_models.remove(model)
        else:
            self.expanded_models.add(model)
        self.render(self.current_project)

    def _progress(
        self,
        parent,
        *,
        percent: float,
        fill: str,
        padx=(10, 10),
        pady=(3, 4),
        height=7,
    ):
        RatioBar(
            parent, percent=percent, fill=fill, height=height
        ).pack(fill="x", padx=padx, pady=pady)

    def _header(
        self,
        parent,
        *,
        left_text: str,
        right_text: str,
        bg: str,
        current: bool,
        command=None,
        left_font=("Segoe UI", 9, "bold"),
        right_font=("Segoe UI", 8),
    ):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=10, pady=(7, 0))

        left = tk.Label(
            row,
            text=left_text,
            bg=bg,
            fg=CURRENT_TEXT if current else TEXT,
            font=left_font,
            anchor="w",
        )
        left.pack(side="left", fill="x", expand=True)

        right = tk.Label(
            row,
            text=right_text,
            bg=bg,
            fg=CURRENT_TEXT if current else MUTED,
            font=right_font,
            anchor="e",
        )
        right.pack(side="right")

        if command:
            for widget in (row, left, right):
                widget.configure(cursor="hand2")
                widget.bind(
                    "<Button-1>",
                    lambda _event: command(),
                )

    def _render_effort(self, parent, effort: dict[str, Any]):
        bg = CURRENT_BG if effort["isCurrent"] else EFFORT_BG
        container = tk.Frame(parent, bg=bg)
        container.pack(fill="x", padx=(18, 10), pady=(4, 5))

        current_suffix = " CURRENT" if effort["isCurrent"] else ""

        self._header(
            container,
            left_text=effort["effort"] + current_suffix,
            right_text=effort_summary_text(effort),
            bg=bg,
            current=effort["isCurrent"],
            left_font=("Segoe UI", 8, "bold"),
            right_font=("Segoe UI", 7),
        )

        self._progress(
            container,
            percent=effort["modelSharePercent"],
            fill=CURRENT_BAR if effort["isCurrent"] else EFFORT_BAR,
            height=6,
        )

        project_line, cache_line = effort_detail_lines(effort)

        tk.Label(
            container,
            text=project_line,
            bg=bg,
            fg=MUTED,
            font=("Segoe UI", 7),
            anchor="w",
        ).pack(fill="x", padx=10)

        tk.Label(
            container,
            text=cache_line,
            bg=bg,
            fg=MUTED,
            font=("Segoe UI", 7),
            anchor="w",
            justify="left",
            wraplength=330,
        ).pack(fill="x", padx=10, pady=(1, 5))

    def render(self, project: dict[str, Any] | None):
        self.current_project = project
        self._clear()

        if not project:
            tk.Label(
                self.inner,
                text="No project selected.",
                bg=BG,
                fg=MUTED,
                font=("Segoe UI", 8),
            ).pack(anchor="w", padx=8, pady=8)
            return

        usage = project.get("usage") or {}
        project_total = _int(usage.get("totalTokens"))
        current_model = project.get("currentModel")
        current_effort = project.get("currentReasoningEffort")

        view = build_model_usage_view(
            project.get("byModelAndEffort") or [],
            project_total,
            current_model=current_model,
            current_effort=current_effort,
        )

        if not self._initialized and current_model:
            self.expanded_models.add(current_model)
            self._initialized = True

        tk.Label(
            self.inner,
            text="Model = project share · Reasoning = model share",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 7),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(7, 6))

        if not view:
            tk.Label(
                self.inner,
                text="No model history available.",
                bg=BG,
                fg=MUTED,
                font=("Segoe UI", 8),
            ).pack(anchor="w", padx=8, pady=8)
            return

        for model in view:
            model_name = model["model"]
            expanded = model_name in self.expanded_models
            bg = CURRENT_BG if model["isCurrent"] else ROW_BG

            card = tk.Frame(
                self.inner,
                bg=bg,
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            card.pack(fill="x", padx=7, pady=(0, 8))

            arrow = "▾" if expanded else "▸"
            current_suffix = " CURRENT" if model["isCurrent"] else ""

            self._header(
                card,
                left_text=f"{arrow} {model_name}{current_suffix}",
                right_text=model_summary_text(model),
                bg=bg,
                current=model["isCurrent"],
                command=lambda name=model_name: self._toggle_model(name),
            )

            self._progress(
                card,
                percent=model["projectSharePercent"],
                fill=CURRENT_BAR if model["isCurrent"] else MODEL_BAR,
                height=8,
            )

            if expanded:
                tk.Label(
                    card,
                    text="Reasoning depth usage",
                    bg=bg,
                    fg=MUTED,
                    font=("Segoe UI", 7, "bold"),
                    anchor="w",
                ).pack(fill="x", padx=18, pady=(3, 0))

                for effort in model["efforts"]:
                    self._render_effort(card, effort)

            tk.Frame(card, bg=bg, height=5).pack()
