import re
from pathlib import Path, PurePosixPath

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


def sanitize_project_folder(value: str) -> str:
    """Return a safe single-folder name for a local CineForge project."""

    return sanitize_output_prefix(value)


def build_project_output_prefix(project_key: str, run_stem: str) -> str:
    """Build the ComfyUI filename_prefix `project-folder/run-stem`.

    ComfyUI save nodes interpret slashes in `filename_prefix` as output
    subfolders. CineForge owns both components, sanitizes them separately,
    and never accepts arbitrary output paths from users.
    """

    return f"{sanitize_project_folder(project_key)}/{sanitize_output_prefix(run_stem)}"


def sanitize_comfy_output_prefix(value: str) -> str:
    """Sanitize a ComfyUI filename_prefix with an optional project folder.

    Accepted shapes are `run-stem` and `project-folder/run-stem` only.
    Absolute paths, backslashes, drive-like prefixes, traversal, and deeper
    directory trees are rejected.
    """

    raw = value.strip()
    if not raw:
        raise UnsafePathError("Output prefix cannot be empty after sanitization")
    if "\\" in raw:
        raise UnsafePathError("Output prefix cannot contain backslashes")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise UnsafePathError("Output prefix cannot be absolute")
    parts = path.parts
    if not 1 <= len(parts) <= 2:
        raise UnsafePathError("Output prefix may only be run-stem or project-folder/run-stem")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise UnsafePathError("Output prefix contains unsafe path component")
    return "/".join(sanitize_output_prefix(part) for part in parts)


def ensure_project_output_dir(root: Path, project_key: str) -> Path:
    """Create and return the safe ComfyUI output directory for one project."""

    project_dir = resolve_inside(root, sanitize_project_folder(project_key))
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


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
