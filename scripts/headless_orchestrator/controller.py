from __future__ import annotations

import json
import hashlib
import re
import uuid
from pathlib import Path

from .ledger import Ledger
from .models import TERMINAL_STATUSES, VALID_TRANSITIONS, TaskSpec, TaskStatus, ToolProfile
from .patches import apply_file_patches
from .policy import assert_task_preflight, capture_worktree_snapshot, resolve_inside, verify_worktree_changes
from .runner import run_worker, validate_json_output
from .schemas import ImplementationResult, parse_implementation_result
from .test_catalog import run_fixed_tests


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._-]{20,}"),
    re.compile(r"(?i)\b(?:xai|openai|anthropic)_api_key\s*[:=]\s*[\"']?[a-z0-9_-]{12,}"),
)


def _contains_secret(value: object) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    return any(pattern.search(serialized) for pattern in _SECRET_PATTERNS)


def _digest_text(value: str) -> dict:
    encoded = value.encode("utf-8")
    return {"present": bool(value), "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}


class HeadlessController:
    def __init__(self, state_root: Path, max_grok_workers: int = 31):
        if not 1 <= max_grok_workers <= 31:
            raise ValueError("max_grok_workers must reserve the 32nd model slot for final review")
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.max_grok_workers = max_grok_workers
        self.ledger = Ledger(state_root / "controller.db")

    def close(self) -> None:
        self.ledger.close()

    def _write_artifact(
        self,
        spec: TaskSpec,
        result,
        parsed: ImplementationResult | None,
        error_type: str | None = None,
        tests: list | None = None,
    ) -> Path:
        artifact_dir = self.state_root / "runs" / spec.run_id / spec.task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact = artifact_dir / "worker-result.json"
        artifact.write_text(
            json.dumps(
                {
                    "pid": result.pid,
                    "exit_code": result.exit_code,
                    "session_id": result.session_id,
                    "timed_out": result.timed_out,
                    "error_type": error_type,
                    "result": parsed.as_dict() if parsed is not None else None,
                    "stderr": _digest_text(result.stderr),
                    "tests": [
                        {
                            "test_id": item.test_id,
                            "exit_code": item.exit_code,
                            "stdout": _digest_text(item.stdout),
                            "stderr": _digest_text(item.stderr),
                        }
                        for item in (tests or [])
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return artifact

    def run_task(self, spec: TaskSpec) -> Path:
        resolve_inside(self.state_root, spec.prompt_file)
        assert_task_preflight(spec.worktree, spec.expected_head, spec.expected_branch)
        self.ledger.create_run(spec.run_id)
        self.ledger.add_task(spec)
        self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.preparing)
        lease_token = str(uuid.uuid4())
        self.ledger.reserve_slot(spec.task_id, lease_token, self.max_grok_workers)
        self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.leased)
        try:
            self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.running)
            before = capture_worktree_snapshot(spec.worktree)
            result = run_worker(
                spec,
                on_started=lambda pid: self.ledger.attach_pid(spec.task_id, pid),
                on_heartbeat=lambda: self.ledger.heartbeat(spec.task_id),
            )
            if result.exit_code != 0 or result.timed_out:
                artifact = self._write_artifact(spec, result, None, error_type="WorkerProcessError")
                self.ledger.complete_task(spec.task_id, result.exit_code, artifact)
                self.ledger.transition(
                    spec.run_id,
                    spec.task_id,
                    TaskStatus.failed,
                    {"exit_code": result.exit_code, "timed_out": result.timed_out},
                )
                raise RuntimeError(f"Grok worker failed with exit code {result.exit_code}")
            try:
                envelope = validate_json_output(result.stdout)
                parsed_result = parse_implementation_result(envelope, result.session_id)
                if _contains_secret(parsed_result.as_dict()):
                    raise RuntimeError("Grok result contained credential-like material")
            except BaseException as error:
                artifact = self._write_artifact(spec, result, None, error_type=type(error).__name__)
                self.ledger.complete_task(spec.task_id, result.exit_code, artifact)
                raise
            artifact = self._write_artifact(spec, result, parsed_result)
            self.ledger.complete_task(spec.task_id, result.exit_code, artifact)
            self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.result_received)
            if parsed_result.status != "completed":
                target = TaskStatus.blocked if parsed_result.status == "blocked" else TaskStatus.failed
                self.ledger.transition(
                    spec.run_id,
                    spec.task_id,
                    target,
                    {"reported_status": parsed_result.status},
                )
                raise RuntimeError(f"Grok reported {parsed_result.status}")
            self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.verifying)
            if spec.tool_profile is ToolProfile.read_only and parsed_result.patches:
                raise RuntimeError("read-only worker returned file patches")
            if spec.tool_profile is ToolProfile.edit_owned:
                apply_file_patches(spec.worktree, parsed_result.patches, spec.owned_paths)
            after = capture_worktree_snapshot(spec.worktree)
            changed_paths = verify_worktree_changes(
                before,
                after,
                spec.owned_paths,
                read_only=spec.tool_profile is ToolProfile.read_only,
            )
            self.ledger.record_event(
                spec.run_id,
                spec.task_id,
                "worktree_verified",
                {"changed_paths": changed_paths},
            )
            test_results = run_fixed_tests(spec.worktree, spec.required_tests)
            artifact = self._write_artifact(spec, result, parsed_result, tests=test_results)
            self.ledger.complete_task(spec.task_id, result.exit_code, artifact)
            failed_tests = [item.test_id for item in test_results if item.exit_code != 0]
            if failed_tests:
                raise RuntimeError(f"controller tests failed: {', '.join(failed_tests)}")
            self.ledger.transition(spec.run_id, spec.task_id, TaskStatus.passed)
            return artifact
        except BaseException as error:
            current = self.ledger.task_status(spec.task_id)
            if current not in TERMINAL_STATUSES and TaskStatus.failed in VALID_TRANSITIONS[current]:
                self.ledger.transition(
                    spec.run_id,
                    spec.task_id,
                    TaskStatus.failed,
                    {"error_type": type(error).__name__},
                )
            raise
        finally:
            self.ledger.release_slot(spec.task_id)

    def invalidate_legacy_task(self, run_id: str, task_id: str, reason: str) -> Path | None:
        record = self.ledger.task_record(task_id)
        if record["run_id"] != run_id:
            raise ValueError("task does not belong to the supplied run")
        artifact_path = Path(record["output_artifact"]) if record["output_artifact"] else None
        if artifact_path is not None and artifact_path.is_file():
            legacy = json.loads(artifact_path.read_text(encoding="utf-8"))
            sanitized = validate_json_output(legacy.get("stdout", "{}")) if "stdout" in legacy else legacy.get("result")
            artifact_path.write_text(
                json.dumps(
                    {
                        "pid": legacy.get("pid"),
                        "exit_code": legacy.get("exit_code"),
                        "session_id": legacy.get("session_id"),
                        "timed_out": legacy.get("timed_out"),
                        "invalidated": True,
                        "reason": reason,
                        "result": sanitized,
                        "stderr": _digest_text(str(legacy.get("stderr", ""))),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        self.ledger.transition(run_id, task_id, TaskStatus.invalidated, {"reason": reason})
        return artifact_path
