from pathlib import Path

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
