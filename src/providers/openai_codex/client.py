from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any


class JsonRpcError(RuntimeError):
    def __init__(self, error: Any):
        self.error = error
        code = error.get("code") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else str(error)
        super().__init__(f"JSON-RPC error {code}: {message}")

    @property
    def code(self) -> int | None:
        if isinstance(self.error, dict):
            value = self.error.get("code")
            return value if isinstance(value, int) else None
        return None


class CodexAppServerClient:
    """Stdlib-only JSONL client for `codex app-server`.

    Authentication stays owned by Codex. This client never opens credential
    files and never reads prompt/source-code content for usage monitoring.
    """

    def __init__(
        self,
        executable: Path,
        codex_home: Path,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.executable = Path(executable)
        self.codex_home = Path(codex_home)
        self.timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self._notifications: deque[dict[str, Any]] = deque()
        self._stderr: deque[str] = deque(maxlen=100)
        self._next_id = 1
        self._write_lock = threading.Lock()

    def __enter__(self) -> "CodexAppServerClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        if not self.executable.is_file():
            raise FileNotFoundError(f"Codex executable not found: {self.executable}")

        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)

        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(
            [str(self.executable), "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )

        assert self._process.stdout is not None
        assert self._process.stderr is not None
        threading.Thread(target=self._stdout_reader, daemon=True).start()
        threading.Thread(target=self._stderr_reader, daemon=True).start()

        init = self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "ai-usage-monitor",
                    "title": "AI Usage Monitor",
                    "version": "0.3.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        if not isinstance(init, dict):
            raise RuntimeError("Codex initialize returned an unexpected response")
        self.notify("initialized", {})

    def _stdout_reader(self) -> None:
        assert self._process is not None
        assert self._process.stdout is not None
        for raw in self._process.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self._messages.put(message)

    def _stderr_reader(self) -> None:
        assert self._process is not None
        assert self._process.stderr is not None
        for raw in self._process.stderr:
            line = raw.rstrip()
            if line:
                self._stderr.append(line)

    def _send(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Codex app-server is not running")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            self._process.stdin.write(payload + "\n")
            self._process.stdin.flush()

    def notify(self, method: str, params: Any | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def _handle_server_request(self, incoming: dict[str, Any]) -> None:
        self._send(
            {
                "id": incoming["id"],
                "error": {
                    "code": -32601,
                    "message": "Client method not supported by AI Usage Monitor",
                },
            }
        )

    def request(self, method: str, params: Any | None = None) -> Any:
        request_id = self._next_id
        self._next_id += 1
        message: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        self._send(message)

        while True:
            try:
                incoming = self._messages.get(timeout=self.timeout_seconds)
            except queue.Empty as exc:
                detail = "\n".join(self._stderr)
                raise TimeoutError(
                    f"Timed out waiting for {method}. App-server stderr:\n{detail}"
                ) from exc

            if incoming.get("id") == request_id and "method" not in incoming:
                if "error" in incoming:
                    raise JsonRpcError(incoming["error"])
                return incoming.get("result")

            if "method" in incoming and "id" not in incoming:
                self._notifications.append(incoming)
                continue

            if "method" in incoming and "id" in incoming:
                self._handle_server_request(incoming)
                continue

            # Unexpected response for another request. Keep it for diagnostics.
            self._notifications.append(
                {"method": "_unexpected/response", "params": incoming}
            )

    def next_notification(self, timeout: float = 1.0) -> dict[str, Any] | None:
        """Return one unsolicited server notification, if available."""
        if self._notifications:
            return self._notifications.popleft()

        deadline_timeout = max(0.0, float(timeout))
        try:
            incoming = self._messages.get(timeout=deadline_timeout)
        except queue.Empty:
            return None

        if "method" in incoming and "id" not in incoming:
            return incoming

        if "method" in incoming and "id" in incoming:
            self._handle_server_request(incoming)
            return None

        # No request should be outstanding while the event monitor calls this.
        # Preserve unexpected messages rather than silently discarding them.
        self._notifications.append(
            {"method": "_unexpected/response", "params": incoming}
        )
        return None

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return

        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    @property
    def stderr_tail(self) -> list[str]:
        return list(self._stderr)
