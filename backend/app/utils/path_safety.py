import re
from pathlib import Path

from backend.app.core.errors import UnsafePathError

_PREFIX_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_output_prefix(value: str) -> str:
    if Path(value).is_absolute() or any(part == ".." for part in Path(value).parts):
        raise UnsafePathError("Output prefix cannot contain path traversal")
    cleaned = _PREFIX_RE.sub("_", value.strip()).strip("._-")
    if not cleaned:
        raise UnsafePathError("Output prefix cannot be empty after sanitization")
    if ".." in cleaned:
        raise UnsafePathError("Output prefix cannot contain traversal")
    return cleaned[:120]


def resolve_inside(root: Path, candidate: str | Path, *, allow_absolute: bool = False) -> Path:
    root_resolved = root.resolve()
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        if not allow_absolute:
            raise UnsafePathError("Absolute paths are not accepted from untrusted input")
        resolved = candidate_path.resolve()
    else:
        resolved = (root_resolved / candidate_path).resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise UnsafePathError(f"Path escapes configured root: {candidate}")
    return resolved


def reject_path_traversal(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise UnsafePathError("Path traversal or absolute path is not allowed")
