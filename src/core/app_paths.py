from __future__ import annotations

import os
import platform
from pathlib import Path


APP_DIR_NAME = "AIUsageMonitor"


def platform_id() -> str:
    system = platform.system().lower()

    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"

    return system or "unknown"


def user_config_dir() -> Path:
    system = platform_id()

    if system == "windows":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        )
        return base / APP_DIR_NAME / "config"

    if system == "macos":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / APP_DIR_NAME
            / "config"
        )

    base = Path(
        os.environ.get(
            "XDG_CONFIG_HOME",
            str(Path.home() / ".config"),
        )
    )
    return base / "ai-usage-monitor"


def user_data_dir() -> Path:
    system = platform_id()

    if system == "windows":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        )
        return base / APP_DIR_NAME / "data"

    if system == "macos":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / APP_DIR_NAME
            / "data"
        )

    base = Path(
        os.environ.get(
            "XDG_DATA_HOME",
            str(Path.home() / ".local" / "share"),
        )
    )
    return base / "ai-usage-monitor"


def user_cache_dir() -> Path:
    system = platform_id()

    if system == "windows":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home() / "AppData" / "Local"),
            )
        )
        return base / APP_DIR_NAME / "cache"

    if system == "macos":
        return Path.home() / "Library" / "Caches" / APP_DIR_NAME

    base = Path(
        os.environ.get(
            "XDG_CACHE_HOME",
            str(Path.home() / ".cache"),
        )
    )
    return base / "ai-usage-monitor"


def private_codex_home() -> Path:
    path = user_data_dir() / "codex-home"
    path.mkdir(parents=True, exist_ok=True)
    return path
