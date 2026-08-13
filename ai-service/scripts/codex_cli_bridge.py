#!/usr/bin/env python3
"""Local development bridge from Dockerized ai-service to host Codex CLI.

Run this on the host machine, not inside Docker. The bridge listens only on
127.0.0.1 by default and executes the OAuth-backed Codex CLI installed with the
ChatGPT desktop app.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_CODEX_BINARY = "/Applications/ChatGPT.app/Contents/Resources/codex"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class CodexBridgeHandler(BaseHTTPRequestHandler):
    server_version = "ReanAI-CodexCLI-Bridge/0.1"

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_json({"status": "healthy"})
            return
        self._send_json({"detail": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/complete":
            self._send_json({"detail": "not found"}, status=404)
            return

        expected_token = os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_TOKEN", "").strip()
        if expected_token:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {expected_token}":
                self._send_json({"detail": "unauthorized"}, status=401)
                return

        try:
            request = self._read_json()
            content = _run_codex_cli(request)
            self._send_json({"content": content})
        except Exception as exc:
            self._send_json({"detail": str(exc)}, status=500)

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.getenv("CODEX_CLI_BRIDGE_QUIET", "false").lower() == "true":
            return
        super().log_message(fmt, *args)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            raise ValueError("request body is required")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _run_codex_cli(request: dict[str, Any]) -> str:
    system_prompt = str(request.get("system_prompt") or "")
    user_prompt = str(request.get("user_prompt") or "")
    timeout = float(request.get("timeout") or os.getenv("VISUAL_TUTOR_CODEX_CLI_TIMEOUT", "90"))
    codex_binary = os.getenv("VISUAL_TUTOR_CODEX_BINARY", DEFAULT_CODEX_BINARY)

    if not system_prompt.strip() or not user_prompt.strip():
        raise ValueError("system_prompt and user_prompt are required")
    if not Path(codex_binary).exists():
        raise FileNotFoundError(f"Codex binary not found: {codex_binary}")

    prompt = (
        f"{system_prompt}\n\n"
        "Return only the strict JSON object for this Visual Tutor turn.\n\n"
        f"Student turn context:\n{user_prompt}"
    )
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as output_file:
        output_path = output_file.name

    try:
        result = subprocess.run(
            [
                codex_binary,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--ignore-rules",
                "-o",
                output_path,
                "-",
            ],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Codex CLI failed with exit code "
                f"{result.returncode}: {result.stderr.strip()}"
            )
        content = Path(output_path).read_text(encoding="utf-8").strip()
        if not content:
            content = _extract_json_object(result.stdout)
        return _extract_json_object(content)
    finally:
        try:
            Path(output_path).unlink()
        except FileNotFoundError:
            pass


def _extract_json_object(output: str) -> str:
    cleaned = output.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Codex CLI output did not contain a JSON object")
    return cleaned[start : end + 1]


def main() -> None:
    host = os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_HOST", DEFAULT_HOST)
    port = int(os.getenv("VISUAL_TUTOR_CODEX_BRIDGE_PORT", str(DEFAULT_PORT)))
    server = ThreadingHTTPServer((host, port), CodexBridgeHandler)
    print(f"Codex CLI bridge listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
