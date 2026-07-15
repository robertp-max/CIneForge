import pytest

from backend.app.core.errors import UnsafePathError
from backend.app.utils.path_safety import (
    build_project_output_prefix,
    ensure_project_output_dir,
    resolve_inside,
    sanitize_comfy_output_prefix,
    sanitize_output_prefix,
)


def test_path_traversal_rejection(tmp_path):
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, "../escape.mp4")


def test_output_prefix_sanitization():
    assert sanitize_output_prefix(" shot 01:/bad name ") == "shot_01_bad_name"
    with pytest.raises(UnsafePathError):
        sanitize_output_prefix("../bad")


def test_comfy_output_prefix_allows_project_folder_only():
    assert sanitize_comfy_output_prefix("Project A/run 01") == "Project_A/run_01"
    assert build_project_output_prefix("My Project", "shot 01") == "My_Project/shot_01"
    with pytest.raises(UnsafePathError):
        sanitize_comfy_output_prefix("Project A/Scene 1/run 01")
    with pytest.raises(UnsafePathError):
        sanitize_comfy_output_prefix("../escape/run")
    with pytest.raises(UnsafePathError):
        sanitize_comfy_output_prefix("C:/escape")


def test_ensure_project_output_dir_stays_inside_root(tmp_path):
    project_dir = ensure_project_output_dir(tmp_path, "My Project")
    assert project_dir == tmp_path / "My_Project"
    assert project_dir.is_dir()
    with pytest.raises(UnsafePathError):
        ensure_project_output_dir(tmp_path, "../escape")

