import pytest

from backend.app.core.errors import UnsafePathError
from backend.app.utils.path_safety import resolve_inside, sanitize_output_prefix


def test_path_traversal_rejection(tmp_path):
    with pytest.raises(UnsafePathError):
        resolve_inside(tmp_path, "../escape.mp4")


def test_output_prefix_sanitization():
    assert sanitize_output_prefix(" shot 01:/bad name ") == "shot_01_bad_name"
    with pytest.raises(UnsafePathError):
        sanitize_output_prefix("../bad")

