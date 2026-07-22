"""Pinned, local-only ComfyUI process supervision.

The supervisor owns only processes it started and recorded.  It never accepts a
command string, downloads dependencies, changes the pinned runtime, or kills an
untracked process.  All mutations require both the hardware-operator gate and
the dedicated auto-start gate (for automatic startup) or an explicit API call.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ValidationError
from backend.app.utils.path_safety import resolve_inside


class ComfyRuntimeMutationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ComfyRuntimeStatus:
    configured: bool
    reachable: bool
    object_info_ready: bool
    base_url: str
    owned_process: bool
    pid: int | None
    hardware_operator_enabled: bool
    autostart_enabled: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "configured": self.configured,
            "reachable": self.reachable,
            "object_info_ready": self.object_info_ready,
            "base_url": self.base_url,
            "owned_process": self.owned_process,
            "pid": self.pid,
            "hardware_operator_enabled": self.hardware_operator_enabled,
            "autostart_enabled": self.autostart_enabled,
            "detail": self.detail,
        }


class PinnedComfyRuntimeManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.runtime_state_root = resolve_inside(self.settings.storage_root, "runtime")
        self.pid_record_path = resolve_inside(self.runtime_state_root, "comfyui_process.json")

    def status(self, *, probe: bool = False) -> ComfyRuntimeStatus:
        pid = self._owned_pid()
        configured = self._runtime_files_exist()
        reachable = False
        object_info_ready = False
        detail = "Live probe not requested."
        if probe:
            try:
                with httpx.Client(
                    base_url=str(self.settings.comfyui_base_url).rstrip("/"),
                    timeout=self.settings.comfyui_request_timeout_sec,
                ) as client:
                    response = client.get("/object_info")
                    response.raise_for_status()
                    payload = response.json()
                    object_info_ready = isinstance(payload, dict) and bool(payload)
                    reachable = True
                    detail = "ComfyUI /object_info is reachable." if object_info_ready else "ComfyUI returned empty object_info."
            except Exception as exc:
                detail = f"ComfyUI probe unavailable: {exc}"
        return ComfyRuntimeStatus(
            configured=configured,
            reachable=reachable,
            object_info_ready=object_info_ready,
            base_url=str(self.settings.comfyui_base_url),
            owned_process=pid is not None,
            pid=pid,
            hardware_operator_enabled=self.settings.hardware_operator_enabled,
            autostart_enabled=self.settings.comfyui_autostart_enabled,
            detail=detail,
        )

    def start(self, *, automatic: bool = False) -> dict[str, object]:
        self._require_mutation_gate(automatic=automatic)
        ready = self.status(probe=True)
        if ready.object_info_ready:
            return {"started": False, "already_ready": True, "status": ready.as_dict()}
        self._validate_runtime_files()
        parsed = self._parsed_local_url()
        if self.pid_record_path.is_file() and self._owned_pid() is None:
            raise ComfyRuntimeMutationBlocked(
                "A foreign or mismatched ComfyUI ownership record exists; operator review is required"
            )
        command = self._launch_command(parsed)
        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen(
            command,
            cwd=self.settings.comfyui_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        self._write_pid_record(process.pid, command)
        deadline = time.monotonic() + self.settings.comfyui_startup_timeout_sec
        last = self.status(probe=True)
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self._clear_pid_record()
                raise RuntimeError(f"Pinned ComfyUI process exited during startup with code {process.returncode}")
            if last.object_info_ready:
                return {"started": True, "already_ready": False, "status": last.as_dict()}
            time.sleep(min(1.0, self.settings.comfyui_progress_poll_interval_sec))
            last = self.status(probe=True)
        self.terminate_process_tree("startup timeout")
        raise TimeoutError(f"ComfyUI did not become ready within {self.settings.comfyui_startup_timeout_sec:g} seconds")

    def restart_pinned_runtime(self) -> dict[str, object]:
        self._require_mutation_gate(automatic=False)
        self.terminate_process_tree("controlled runtime restart")
        return self.start(automatic=False)

    def terminate_process_tree(self, reason: str) -> dict[str, object]:
        self._require_mutation_gate(automatic=False)
        pid = self._owned_pid()
        if pid is None:
            return {"terminated": False, "reason": reason, "detail": "No owned ComfyUI process is recorded."}
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode not in {0, 128}:
                # Retain the ownership record when termination fails. Losing
                # it would make a still-running child impossible to manage
                # safely on the next explicit operator attempt.
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "taskkill failed")
        else:
            os.kill(pid, 15)
        self._clear_pid_record()
        return {"terminated": True, "pid": pid, "reason": reason}

    def health_check(self) -> dict[str, object]:
        status = self.status(probe=True)
        return {"status": "ok" if status.object_info_ready else "unavailable", **status.as_dict()}

    def _require_mutation_gate(self, *, automatic: bool) -> None:
        if not self.settings.hardware_operator_enabled:
            raise ComfyRuntimeMutationBlocked(
                "Pinned ComfyUI process mutation requires CINEFORGE_HARDWARE_OPERATOR_ENABLED=true"
            )
        if automatic and not self.settings.comfyui_autostart_enabled:
            raise ComfyRuntimeMutationBlocked(
                "Automatic ComfyUI startup requires CINEFORGE_COMFYUI_AUTOSTART_ENABLED=true"
            )

    def _parsed_local_url(self):
        parsed = urlparse(str(self.settings.comfyui_base_url))
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValidationError("Managed ComfyUI runtime URL must be localhost-only")
        return parsed

    def _launch_command(self, parsed=None) -> list[str]:
        parsed = parsed or self._parsed_local_url()
        return [
            str(self.settings.comfyui_python_executable),
            "-s",
            str(self.settings.comfyui_main_script),
            "--windows-standalone-build",
            "--disable-api-nodes",
            "--listen",
            parsed.hostname or "127.0.0.1",
            "--port",
            str(parsed.port or 8188),
            "--disable-auto-launch",
        ]

    def _runtime_files_exist(self) -> bool:
        return (
            self.settings.comfyui_root.is_dir()
            and self.settings.comfyui_python_executable.is_file()
            and self.settings.comfyui_main_script.is_file()
        )

    def _validate_runtime_files(self) -> None:
        self._parsed_local_url()
        if not self.settings.comfyui_root.is_dir():
            raise FileNotFoundError(self.settings.comfyui_root)
        if not self.settings.comfyui_python_executable.is_file():
            raise FileNotFoundError(self.settings.comfyui_python_executable)
        if not self.settings.comfyui_main_script.is_file():
            raise FileNotFoundError(self.settings.comfyui_main_script)
        if self.settings.comfyui_main_script.parent.resolve() != self.settings.comfyui_root.resolve():
            raise ValidationError("Pinned ComfyUI main.py must be directly inside comfyui_root")

    def _owned_pid(self) -> int | None:
        if not self.pid_record_path.is_file():
            return None
        try:
            payload = json.loads(self.pid_record_path.read_text(encoding="utf-8"))
            expected_command = self._launch_command()
            if payload.get("hostname") != socket.gethostname():
                return None
            if payload.get("runtime_root") != str(self.settings.comfyui_root):
                return None
            if payload.get("base_url") != str(self.settings.comfyui_base_url):
                return None
            if payload.get("command") != expected_command:
                return None
            pid = int(payload["pid"])
            if pid < 1 or not self._pid_exists(pid):
                self._clear_pid_record()
                return None
            return pid
        except Exception:
            # A corrupt or unreadable record is not proof that the recorded
            # process is gone. Keep the record so every mutation fails closed
            # until an operator inspects it; only a positively stale PID may
            # clear ownership automatically above.
            return None

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                return result.returncode == 0 and str(pid) in result.stdout
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _write_pid_record(self, pid: int, command: list[str]) -> None:
        self.runtime_state_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": pid,
            "started_at": datetime.now(UTC).isoformat(),
            "base_url": str(self.settings.comfyui_base_url),
            "runtime_root": str(self.settings.comfyui_root),
            "command": command,
            "hostname": socket.gethostname(),
        }
        temporary = self.pid_record_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.pid_record_path)

    def _clear_pid_record(self) -> None:
        self.pid_record_path.unlink(missing_ok=True)
