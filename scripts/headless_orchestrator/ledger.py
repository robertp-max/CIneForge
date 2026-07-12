from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .models import TaskSpec, TaskStatus, VALID_TRANSITIONS


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Ledger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                worktree TEXT NOT NULL,
                owned_paths_json TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 0,
                output_artifact TEXT,
                exit_code INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS process_leases (
                task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
                lease_token TEXT NOT NULL UNIQUE,
                pid INTEGER,
                acquired_at TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    @contextmanager
    def immediate_transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def create_run(self, run_id: str) -> None:
        now = _now()
        self.connection.execute(
            "INSERT OR IGNORE INTO runs(id, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
            (run_id, now, now),
        )

    def add_task(self, spec: TaskSpec) -> None:
        now = _now()
        self.connection.execute(
            """
            INSERT INTO tasks(id, run_id, role, status, worktree, owned_paths_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                spec.task_id,
                spec.run_id,
                spec.role,
                TaskStatus.queued,
                str(spec.worktree),
                json.dumps(spec.owned_paths),
                now,
                now,
            ),
        )
        self.record_event(spec.run_id, spec.task_id, "task_created", {"role": spec.role})

    def task_status(self, task_id: str) -> TaskStatus:
        row = self.connection.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown task: {task_id}")
        return TaskStatus(row["status"])

    def transition(self, run_id: str, task_id: str, target: TaskStatus, details: dict | None = None) -> None:
        current = self.task_status(task_id)
        if target not in VALID_TRANSITIONS[current]:
            raise ValueError(f"invalid task transition: {current} -> {target}")
        self.connection.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (target, _now(), task_id),
        )
        self.record_event(run_id, task_id, "task_transition", {"from": current, "to": target, **(details or {})})

    def reserve_slot(self, task_id: str, lease_token: str, max_active: int = 47) -> None:
        if not 1 <= max_active <= 47:
            raise ValueError("max_active must be between 1 and 47")
        with self.immediate_transaction():
            active = self.connection.execute("SELECT COUNT(*) FROM process_leases").fetchone()[0]
            if active >= max_active:
                raise RuntimeError(f"worker limit reached: {active}/{max_active}")
            now = _now()
            self.connection.execute(
                "INSERT INTO process_leases(task_id, lease_token, acquired_at, heartbeat_at) VALUES (?, ?, ?, ?)",
                (task_id, lease_token, now, now),
            )

    def attach_pid(self, task_id: str, pid: int) -> None:
        self.connection.execute(
            "UPDATE process_leases SET pid = ?, heartbeat_at = ? WHERE task_id = ?",
            (pid, _now(), task_id),
        )

    def heartbeat(self, task_id: str) -> None:
        self.connection.execute(
            "UPDATE process_leases SET heartbeat_at = ? WHERE task_id = ?",
            (_now(), task_id),
        )

    def release_slot(self, task_id: str) -> None:
        self.connection.execute("DELETE FROM process_leases WHERE task_id = ?", (task_id,))

    def complete_task(self, task_id: str, exit_code: int, output_artifact: Path | None) -> None:
        self.connection.execute(
            "UPDATE tasks SET exit_code = ?, output_artifact = ?, updated_at = ? WHERE id = ?",
            (exit_code, str(output_artifact) if output_artifact else None, _now(), task_id),
        )

    def record_event(self, run_id: str, task_id: str | None, event_type: str, details: dict) -> None:
        self.connection.execute(
            "INSERT INTO events(run_id, task_id, event_type, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, task_id, event_type, json.dumps(details, default=str, sort_keys=True), _now()),
        )

    def list_tasks(self, run_id: str | None = None) -> list[dict]:
        if run_id:
            rows = self.connection.execute("SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at", (run_id,))
        else:
            rows = self.connection.execute("SELECT * FROM tasks ORDER BY created_at")
        return [dict(row) for row in rows]

    def task_record(self, task_id: str) -> dict:
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown task: {task_id}")
        return dict(row)
