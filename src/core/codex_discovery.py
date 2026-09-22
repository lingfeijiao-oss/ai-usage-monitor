from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


WINDOWS_DRIVE_FIXED = 3

PRUNE_NAMES = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "winsxs",
    "node_modules",
    ".git",
    "__pycache__",
    "proc",
    "sys",
    "dev",
}


@dataclass(frozen=True)
class CodexInstall:
    executable: str
    version: str
    app_server: bool
    discovery_source: str


@dataclass(frozen=True)
class CodexProfile:
    path: str
    discovery_source: str


def _system() -> str:
    return platform.system().lower()


def _dedupe_path_pairs(
    items: Iterable[tuple[Path, str]],
) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    seen: set[str] = set()

    for path, source in items:
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path).casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append((path, source))

    return result


def windows_fixed_drive_roots() -> list[Path]:
    if _system() != "windows":
        return []

    mask = ctypes.windll.kernel32.GetLogicalDrives()
    get_type = ctypes.windll.kernel32.GetDriveTypeW

    roots: list[Path] = []

    for index in range(26):
        if not (mask & (1 << index)):
            continue

        letter = chr(ord("A") + index)
        root = f"{letter}:\\"

        if get_type(root) == WINDOWS_DRIVE_FIXED:
            roots.append(Path(root))

    return roots


def scan_roots() -> list[Path]:
    system = _system()
    home = Path.home()

    if system == "windows":
        return windows_fixed_drive_roots()

    if system == "darwin":
        roots = [
            home,
            Path("/Applications"),
            Path("/usr/local"),
            Path("/opt"),
            Path("/Volumes"),
        ]
    else:
        roots = [
            home,
            Path("/usr/local"),
            Path("/opt"),
            Path("/mnt"),
            Path("/media"),
            Path("/run/media"),
        ]

    result = []

    for path in roots:
        if path.exists():
            result.append(path)

    return result


def _candidate_from_command(command: str) -> Path | None:
    value = shutil.which(command)
    return Path(value) if value else None


def fast_install_candidates() -> list[tuple[Path, str]]:
    system = _system()
    user = Path.home()
    items: list[tuple[Path, str]] = []

    commands = (
        ("codex.exe", "codex.cmd", "codex")
        if system == "windows"
        else ("codex",)
    )

    for command in commands:
        candidate = _candidate_from_command(command)

        if candidate:
            items.append((candidate, "PATH"))

    install_dir = os.environ.get("CODEX_INSTALL_DIR")

    if install_dir:
        for name in commands:
            items.append(
                (
                    Path(install_dir) / name,
                    "CODEX_INSTALL_DIR",
                )
            )

    if system == "windows":
        local = Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(user / "AppData" / "Local"),
            )
        )

        roaming = Path(
            os.environ.get(
                "APPDATA",
                str(user / "AppData" / "Roaming"),
            )
        )

        known = [
            user / ".local" / "bin" / "codex.exe",
            roaming / "npm" / "codex.cmd",
            local / "Programs" / "codex" / "codex.exe",
            local / "OpenAI" / "codex" / "codex.exe",
        ]

        for root in windows_fixed_drive_roots():
            known.extend(
                [
                    root / "OpenAI" / "Codex" / "codex.exe",
                    root / "OpenAI" / "CodexMonitorRuntime" / "bin" / "codex.exe",
                    root / "Codex" / "codex.exe",
                    root / "Tools" / "Codex" / "codex.exe",
                ]
            )

    elif system == "darwin":
        known = [
            user / ".local" / "bin" / "codex",
            user / ".npm-global" / "bin" / "codex",
            user / ".bun" / "bin" / "codex",
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
            Path("/usr/bin/codex"),
            Path("/opt/codex/bin/codex"),
        ]

    else:
        known = [
            user / ".local" / "bin" / "codex",
            user / ".npm-global" / "bin" / "codex",
            user / ".bun" / "bin" / "codex",
            Path("/usr/local/bin/codex"),
            Path("/usr/bin/codex"),
            Path("/opt/codex/bin/codex"),
        ]

    items.extend(
        (path, "COMMON_LOCATION")
        for path in known
    )

    return _dedupe_path_pairs(items)


def profile_root_candidates() -> list[tuple[Path, str]]:
    system = _system()
    items: list[tuple[Path, str]] = []

    env_home = os.environ.get("CODEX_HOME")

    if env_home:
        items.append(
            (
                Path(env_home),
                "CODEX_HOME",
            )
        )

    items.append(
        (
            Path.home() / ".codex",
            "USER_HOME",
        )
    )

    if system == "windows":
        for root in windows_fixed_drive_roots():
            items.append(
                (
                    root / ".codex",
                    "FIXED_DRIVE_ROOT",
                )
            )

    elif system == "darwin":
        volumes = Path("/Volumes")

        if volumes.is_dir():
            try:
                for volume in volumes.iterdir():
                    items.append(
                        (
                            volume / ".codex",
                            "MOUNTED_VOLUME_ROOT",
                        )
                    )
            except OSError:
                pass

    else:
        user = Path.home().name

        for parent in (
            Path("/mnt"),
            Path("/media") / user,
            Path("/run/media") / user,
        ):
            if not parent.is_dir():
                continue

            try:
                for mounted in parent.iterdir():
                    items.append(
                        (
                            mounted / ".codex",
                            "MOUNTED_VOLUME_ROOT",
                        )
                    )
            except OSError:
                pass

    return _dedupe_path_pairs(items)


def _creationflags() -> int:
    if (
        _system() == "windows"
        and hasattr(subprocess, "CREATE_NO_WINDOW")
    ):
        return subprocess.CREATE_NO_WINDOW

    return 0


def _run_identity(
    executable: Path,
    timeout: float = 5.0,
) -> CodexInstall | None:
    if not executable.exists() or executable.is_dir():
        return None

    try:
        version = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_creationflags(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    text = (
        version.stdout
        or version.stderr
        or ""
    ).strip()

    if (
        version.returncode != 0
        or "codex" not in text.casefold()
    ):
        return None

    try:
        app = subprocess.run(
            [
                str(executable),
                "app-server",
                "--help",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_creationflags(),
            check=False,
        )

        app_server = app.returncode == 0

    except (OSError, subprocess.SubprocessError):
        app_server = False

    return CodexInstall(
        executable=str(executable),
        version=text,
        app_server=app_server,
        discovery_source="validated",
    )


def validate_install_candidate(
    path: Path,
    source: str,
) -> CodexInstall | None:
    validated = _run_identity(path)

    if validated is None:
        return None

    return CodexInstall(
        executable=validated.executable,
        version=validated.version,
        app_server=validated.app_server,
        discovery_source=source,
    )


def _version_rank(
    version: str,
) -> tuple[int, tuple[int, ...]]:
    lowered = version.casefold()

    stable = 0 if any(
        marker in lowered
        for marker in (
            "alpha",
            "beta",
            "rc",
            "dev",
            "nightly",
            "preview",
        )
    ) else 1

    match = re.search(
        r"(\d+(?:\.\d+)+)",
        version,
    )

    numeric = (
        tuple(
            int(part)
            for part in match.group(1).split(".")
        )
        if match
        else ()
    )

    return stable, numeric


def _source_rank(
    source: str,
) -> int:
    return {
        "PATH": 60,
        "CODEX_INSTALL_DIR": 55,
        "COMMON_LOCATION": 50,
        "validated": 40,
        "BOUNDED_LOCAL_SCAN": 10,
    }.get(source, 0)


def _path_role_rank(
    executable: str,
) -> int:
    path = executable.casefold().replace(
        "/",
        "\\",
    )

    if "\\.sandbox-bin\\" in path:
        return -100

    if "\\plugins\\.plugin-appserver\\" in path:
        return -90

    if "\\.plugin-appserver\\" in path:
        return -80

    if "\\plugins\\" in path:
        return -40

    return 0


def install_rank(
    item: CodexInstall,
) -> tuple:
    stable, numeric = _version_rank(
        item.version
    )

    return (
        1 if item.app_server else 0,
        _path_role_rank(item.executable),
        stable,
        numeric,
        _source_rank(item.discovery_source),
        item.executable.casefold(),
    )


def bounded_local_scan(
    *,
    max_depth: int = 6,
    time_budget_seconds: float = 15.0,
) -> list[tuple[Path, str]]:
    system = _system()

    wanted = (
        {"codex.exe", "codex.cmd"}
        if system == "windows"
        else {"codex"}
    )

    deadline = time.monotonic() + max(
        1.0,
        time_budget_seconds,
    )

    found: list[tuple[Path, str]] = []

    for root in scan_roots():
        if time.monotonic() >= deadline:
            break

        stack: list[tuple[Path, int]] = [
            (root, 0)
        ]

        while (
            stack
            and time.monotonic() < deadline
        ):
            current, depth = stack.pop()

            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if time.monotonic() >= deadline:
                            break

                        name = entry.name.casefold()

                        try:
                            if entry.is_file(
                                follow_symlinks=False
                            ):
                                if name in wanted:
                                    found.append(
                                        (
                                            Path(entry.path),
                                            "BOUNDED_LOCAL_SCAN",
                                        )
                                    )

                                continue

                            if not entry.is_dir(
                                follow_symlinks=False
                            ):
                                continue

                        except OSError:
                            continue

                        if depth >= max_depth:
                            continue

                        if name in PRUNE_NAMES:
                            continue

                        stack.append(
                            (
                                Path(entry.path),
                                depth + 1,
                            )
                        )

            except (OSError, PermissionError):
                continue

    return _dedupe_path_pairs(found)


def discover_installations(
    *,
    allow_fallback_scan: bool = True,
) -> list[CodexInstall]:
    validated: list[CodexInstall] = []
    seen: set[str] = set()

    candidates = fast_install_candidates()

    if allow_fallback_scan:
        candidates.extend(
            bounded_local_scan()
        )

    for path, source in _dedupe_path_pairs(
        candidates
    ):
        install = validate_install_candidate(
            path,
            source,
        )

        if install is None:
            continue

        key = str(
            Path(install.executable)
        ).casefold()

        if key in seen:
            continue

        seen.add(key)
        validated.append(install)

    validated.sort(
        key=install_rank,
        reverse=True,
    )

    return validated


def discover_profiles(
    validated_installs: list[CodexInstall] | None = None,
) -> list[CodexProfile]:
    candidates = profile_root_candidates()

    if validated_installs:
        for item in validated_installs:
            exe = Path(item.executable)

            candidates.extend(
                [
                    (
                        exe.parent / ".codex",
                        "INSTALL_NEARBY",
                    ),
                    (
                        exe.parent.parent / "home",
                        "INSTALL_NEARBY",
                    ),
                ]
            )

    profiles: list[CodexProfile] = []
    seen: set[str] = set()

    for path, source in _dedupe_path_pairs(
        candidates
    ):
        if not path.is_dir():
            continue

        try:
            key = str(
                path.resolve()
            ).casefold()

        except OSError:
            key = str(
                path
            ).casefold()

        if key in seen:
            continue

        seen.add(key)

        profiles.append(
            CodexProfile(
                path=str(path),
                discovery_source=source,
            )
        )

    return profiles


def choose_install(
    installs: list[CodexInstall],
) -> CodexInstall | None:
    if not installs:
        return None

    compatible = [
        item
        for item in installs
        if item.app_server
    ]

    pool = (
        compatible
        if compatible
        else installs
    )

    return max(
        pool,
        key=install_rank,
    )
