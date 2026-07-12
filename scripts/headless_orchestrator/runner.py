from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import TaskSpec
from .policy import build_child_environment
from .schemas import RESULT_SCHEMA_JSON
from .windows_job import WindowsJob


DEFAULT_GROK_EXE = Path(r"C:\Users\razer\.grok\bin\grok.exe")
DEFAULT_GROK_SHA256 = "1E9393391A399275A1863F9F457E86C5D904B10B9CBA987D0B81F8427FA625F2"
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class WorkerResult:
    pid: int
    exit_code: int
    stdout: str
    stderr: str
    session_id: str
    timed_out: bool = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_grok_executable(path: Path = DEFAULT_GROK_EXE, expected_sha256: str = DEFAULT_GROK_SHA256) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Grok executable not found: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256.upper():
        raise RuntimeError(f"Grok executable hash mismatch: expected {expected_sha256}, got {actual}")


def verify_no_mcp_servers(grok_exe: Path = DEFAULT_GROK_EXE) -> None:
    result = subprocess.run(
        [str(grok_exe), "mcp", "list"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        env=build_child_environment(),
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0 or "No MCP servers configured." not in result.stdout:
        raise RuntimeError("Grok MCP configuration must be empty for headless workers")


def build_worker_args(spec: TaskSpec, session_id: str, grok_exe: Path = DEFAULT_GROK_EXE) -> list[str]:
    prompt_file = spec.prompt_file.resolve(strict=True)
    return [
        str(grok_exe),
        "--prompt-file",
        str(prompt_file),
        "--verbatim",
        "--model",
        "grok-4.5",
        "--reasoning-effort",
        "high",
        "--cwd",
        str(spec.worktree.resolve()),
        "--session-id",
        session_id,
        "--json-schema",
        RESULT_SCHEMA_JSON,
        "--max-turns",
        str(spec.max_turns),
        "--no-subagents",
        "--no-memory",
        "--no-ask-user",
        "--disable-web-search",
        "--no-auto-update",
        "--permission-mode",
        "default",
        "--tools",
        "todo_write",
        "--disallowed-tools",
        "Agent,task,todo_write,run_terminal_cmd,read_file,grep,list_dir,search_replace,web_search,web_fetch",
    ]


def run_worker(
    spec: TaskSpec,
    grok_exe: Path = DEFAULT_GROK_EXE,
    expected_sha256: str = DEFAULT_GROK_SHA256,
    on_started: Callable[[int], None] | None = None,
    on_heartbeat: Callable[[], None] | None = None,
) -> WorkerResult:
    verify_grok_executable(grok_exe, expected_sha256)
    verify_no_mcp_servers(grok_exe)
    if not spec.worktree.is_dir() or not (spec.worktree / ".git").exists():
        raise ValueError(f"not a Git worktree: {spec.worktree}")
    session_id = str(uuid.uuid4())
    args = build_worker_args(spec, session_id, grok_exe)
    launcher = Path(__file__).with_name("launcher.py").resolve(strict=True)
    launch_args = [sys.executable, str(launcher), *args]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    timed_out = False
    output_exceeded = False
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    byte_count = [0]
    count_lock = threading.Lock()

    def capture(stream, chunks: list[bytes], job: WindowsJob) -> None:
        nonlocal output_exceeded
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            with count_lock:
                byte_count[0] += len(chunk)
                if byte_count[0] > MAX_OUTPUT_BYTES:
                    output_exceeded = True
                    job.close()
                    return
                chunks.append(chunk)

    with WindowsJob() as job:
        try:
            process = subprocess.Popen(
                launch_args,
                cwd=spec.worktree,
                env=build_child_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                shell=False,
                creationflags=creationflags,
            )
            try:
                if os.name == "nt":
                    job.assign(process._handle)  # type: ignore[attr-defined]
            except BaseException:
                process.kill()
                process.wait(timeout=10)
                raise
            if on_started is not None:
                on_started(process.pid)
            process.stdin.write(b"1")
            process.stdin.flush()
            process.stdin.close()
            stdout_thread = threading.Thread(
                target=capture,
                args=(process.stdout, stdout_chunks, job),
                name=f"grok-stdout-{process.pid}",
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=capture,
                args=(process.stderr, stderr_chunks, job),
                name=f"grok-stderr-{process.pid}",
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()
            deadline = time.monotonic() + spec.timeout_sec
            heartbeat_at = time.monotonic() + 10
            while process.poll() is None:
                now = time.monotonic()
                if output_exceeded:
                    process.kill()
                    break
                if now >= deadline:
                    timed_out = True
                    job.close()
                    process.kill()
                    break
                if on_heartbeat is not None and now >= heartbeat_at:
                    on_heartbeat()
                    heartbeat_at = now + 10
                try:
                    process.wait(timeout=min(1.0, max(0.01, deadline - now)))
                except subprocess.TimeoutExpired:
                    pass
            process.wait(timeout=10)
            stdout_thread.join(timeout=10)
            stderr_thread.join(timeout=10)
        finally:
            if "process" in locals() and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    if output_exceeded:
        raise RuntimeError("Grok output exceeded the configured size limit")
    return WorkerResult(
        pid=process.pid,
        exit_code=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
        session_id=session_id,
        timed_out=timed_out,
    )


SENSITIVE_RESULT_KEYS = {
    "analysis",
    "chain_of_thought",
    "reasoning",
    "reasoning_content",
    "thinking",
    "thought",
    "thoughts",
}


def _sanitize_result(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _sanitize_result(item)
            for key, item in value.items()
            if key.casefold() not in SENSITIVE_RESULT_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_result(item) for item in value]
    return value


def validate_json_output(output: str) -> object:
    if not output.strip():
        raise ValueError("Grok returned no stdout")
    return _sanitize_result(json.loads(output))
