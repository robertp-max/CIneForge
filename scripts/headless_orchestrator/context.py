from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .policy import normalize_relative_path, resolve_inside


MAX_CONTEXT_BYTES = 8 * 1024 * 1024


def _tracked_paths(worktree: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        shell=False,
    )
    return {item.replace("\\", "/").casefold() for item in result.stdout.split("\0") if item}


def build_context_prompt(
    worktree: Path,
    template_file: Path,
    context_paths: tuple[str, ...],
    output_file: Path,
    output_root: Path,
) -> Path:
    root = worktree.resolve(strict=True)
    template_candidate = template_file if template_file.is_absolute() else root / template_file
    template = resolve_inside(root, template_candidate)
    if not template.is_file():
        raise FileNotFoundError(f"prompt template not found: {template}")
    tracked = _tracked_paths(root)
    sections = [template.read_text(encoding="utf-8"), "\n\n<controller_context>"]
    total_bytes = len(sections[0].encode("utf-8"))
    seen: set[str] = set()
    for supplied in context_paths:
        relative = normalize_relative_path(supplied)
        if relative in seen:
            raise ValueError(f"duplicate context path: {supplied}")
        if relative.casefold() not in tracked:
            raise ValueError(f"context path must be a tracked file: {supplied}")
        seen.add(relative)
        path = resolve_inside(root, root / relative)
        content = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        section = (
            f'\n<file path="{relative}" sha256="{digest}">\n'
            f"{content}\n"
            "</file>"
        )
        total_bytes += len(section.encode("utf-8"))
        if total_bytes > MAX_CONTEXT_BYTES:
            raise RuntimeError("controller context bundle exceeded its size limit")
        sections.append(section)
    sections.append("\n</controller_context>\n")
    output_root.mkdir(parents=True, exist_ok=True)
    candidate_output = output_file if output_file.is_absolute() else output_root / output_file
    resolved_output = resolve_inside(output_root, candidate_output)
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text("".join(sections), encoding="utf-8")
    return resolved_output
