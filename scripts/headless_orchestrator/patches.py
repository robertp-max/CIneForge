from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .policy import assert_owned_paths, normalize_relative_path, resolve_inside
from .schemas import FilePatch


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def apply_file_patches(worktree: Path, patches: tuple[FilePatch, ...], owned_paths: tuple[str, ...]) -> list[str]:
    relative_paths = [normalize_relative_path(patch.path) for patch in patches]
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError("a worker returned duplicate patch paths")
    assert_owned_paths(relative_paths, owned_paths)
    prepared: list[tuple[FilePatch, Path, bytes | None]] = []
    for patch, relative in zip(patches, relative_paths, strict=True):
        target = resolve_inside(worktree, worktree / relative)
        original = target.read_bytes() if target.is_file() else None
        if patch.action == "create":
            if original is not None or target.exists():
                raise ValueError(f"create patch target already exists: {relative}")
        else:
            if original is None:
                raise ValueError(f"replace patch target is not a file: {relative}")
            if _sha256_bytes(original).casefold() != str(patch.expected_sha256).casefold():
                raise ValueError(f"replace patch is stale: {relative}")
        prepared.append((patch, target, original))

    applied: list[tuple[Path, bytes | None]] = []
    try:
        for patch, target, original in prepared:
            target.parent.mkdir(parents=True, exist_ok=True)
            resolve_inside(worktree, target.parent)
            fd, temporary_name = tempfile.mkstemp(prefix=".grok-patch-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(patch.content.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_name, target)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
            applied.append((target, original))
    except BaseException:
        for target, original in reversed(applied):
            if original is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(original)
        raise
    return relative_paths
