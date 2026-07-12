from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


ENV_ALLOWLIST = {
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERDOMAIN",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
}

FORBIDDEN_PARTS = {".git", ".env", ".venv", "node_modules", "__pycache__"}


def build_child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    source = source or dict(os.environ)
    result = {key: value for key, value in source.items() if key.upper() in ENV_ALLOWLIST}
    result.update({"NO_COLOR": "1", "RUST_LOG": "error"})
    return result


def resolve_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    unresolved = candidate.absolute()
    current = resolved_root
    try:
        relative_parts = unresolved.relative_to(resolved_root).parts
    except ValueError as error:
        raise ValueError(f"path escapes assigned worktree: {candidate}") from error
    for part in relative_parts:
        current = current / part
        if current.exists() and _is_reparse_point(current):
            raise ValueError(f"reparse points are forbidden in worker paths: {candidate}")
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"path escapes assigned worktree: {candidate}") from error
    return resolved_candidate


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & 0x400)


def normalize_relative_path(path: str) -> str:
    windows_path = PureWindowsPath(path)
    posix_path = PurePosixPath(path.replace("\\", "/"))
    if windows_path.is_absolute() or windows_path.drive or windows_path.root or posix_path.is_absolute():
        raise ValueError(f"absolute paths are forbidden: {path}")
    normalized = str(PurePosixPath(path.replace("\\", "/"))).lower()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("../") or normalized == "..":
        raise ValueError(f"relative path escapes ownership boundary: {path}")
    if any(part.lower() in FORBIDDEN_PARTS for part in PurePosixPath(normalized).parts):
        raise ValueError(f"forbidden path: {path}")
    return normalized


def path_is_owned(path: str, owned_patterns: tuple[str, ...]) -> bool:
    normalized = normalize_relative_path(path)
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/").lower()) for pattern in owned_patterns)


def assert_owned_paths(paths: list[str], owned_patterns: tuple[str, ...]) -> None:
    unexpected = [path for path in paths if not path_is_owned(path, owned_patterns)]
    if unexpected:
        raise ValueError(f"changes outside task ownership: {', '.join(sorted(unexpected))}")


@dataclass(frozen=True, slots=True)
class WorktreeSnapshot:
    branch: str
    head: str
    files: dict[str, str]


def _git(worktree: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(worktree), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        shell=False,
    )
    return result.stdout


def _content_digest(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if not path.is_file():
        return "non-file"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_worktree_snapshot(worktree: Path) -> WorktreeSnapshot:
    """Hash tracked, untracked, and ignored files without following reparse points."""

    root = worktree.resolve(strict=True)
    listed = _git(root, "ls-files", "-z", "--cached")
    relative_paths = {item for item in listed.split("\0") if item}
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        retained_directories: list[str] = []
        for name in directory_names:
            child = directory_path / name
            if name == ".git":
                continue
            if _is_reparse_point(child):
                raise ValueError(f"reparse points are forbidden in worker worktrees: {child}")
            retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            child = directory_path / name
            relative = child.relative_to(root).as_posix()
            if relative != ".git":
                relative_paths.add(relative)
    relative_paths.add(".git")
    files: dict[str, str] = {}
    for relative in sorted(relative_paths, key=str.casefold):
        normalized = relative.replace("\\", "/")
        candidate = root / relative
        if normalized != ".git":
            resolve_inside(root, candidate)
        files[normalized] = _content_digest(candidate)
    return WorktreeSnapshot(
        branch=_git(root, "branch", "--show-current").strip(),
        head=_git(root, "rev-parse", "HEAD").strip(),
        files=files,
    )


def assert_task_preflight(worktree: Path, expected_head: str, expected_branch: str) -> None:
    root = worktree.resolve(strict=True)
    if not (root / ".git").is_file():
        raise ValueError("worker must use a dedicated linked Git worktree")
    actual_head = _git(root, "rev-parse", "HEAD").strip()
    actual_branch = _git(root, "branch", "--show-current").strip()
    if actual_head != expected_head or actual_branch != expected_branch:
        raise RuntimeError("worker worktree is on an unexpected branch or SHA")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise RuntimeError("worker worktree must be clean before launch")


def verify_worktree_changes(
    before: WorktreeSnapshot,
    after: WorktreeSnapshot,
    owned_patterns: tuple[str, ...],
    read_only: bool,
) -> list[str]:
    if before.branch != after.branch or before.head != after.head:
        raise RuntimeError("worker changed the Git branch or HEAD")
    paths = set(before.files) | set(after.files)
    changed = sorted(path for path in paths if before.files.get(path) != after.files.get(path))
    if read_only and changed:
        raise RuntimeError(f"read-only worker changed files: {', '.join(changed)}")
    if changed:
        assert_owned_paths(changed, owned_patterns)
    return changed
