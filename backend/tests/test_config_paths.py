from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.core.config import REPO_ROOT, Settings


def test_relative_storage_and_sqlite_paths_resolve_from_repo_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        _env_file=None,
        storage_root="./storage",
        database_url="sqlite:///./storage/cineforge_local.db",
    )

    assert settings.storage_root == (REPO_ROOT / "storage").resolve()
    expected_db = (REPO_ROOT / "storage" / "cineforge_local.db").resolve().as_posix()
    assert settings.database_url == f"sqlite:///{expected_db}"
    assert settings.storage_root.is_absolute()


def test_absolute_storage_root_is_preserved(tmp_path):
    root = (tmp_path / "managed").resolve()
    settings = Settings(
        _env_file=None,
        storage_root=root,
        database_url="sqlite://",
    )

    assert settings.storage_root == root
    assert settings.database_url == "sqlite://"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:8188",
        "http://comfy.example:8188",
        "http://127.0.0.1:8188/api",
        "http://user:password@127.0.0.1:8188",
    ],
)
def test_comfyui_base_url_rejects_non_local_or_ambiguous_urls(base_url: str):
    with pytest.raises(ValidationError, match="comfyui_base_url"):
        Settings(_env_file=None, comfyui_base_url=base_url)


@pytest.mark.parametrize(
    "base_url",
    ["http://127.0.0.1:8188", "http://localhost:8188", "http://[::1]:8188"],
)
def test_comfyui_base_url_accepts_loopback_http(base_url: str):
    assert Settings(_env_file=None, comfyui_base_url=base_url).comfyui_base_url is not None
