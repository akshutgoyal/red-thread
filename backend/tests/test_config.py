import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT, Settings


def test_blank_path_settings_use_project_defaults(monkeypatch):
    monkeypatch.setenv("RED_THREAD_DATA_DIR", "")
    monkeypatch.setenv("RED_THREAD_REPORTS_DIR", "")
    monkeypatch.setenv("RED_THREAD_DATABASE_URL", "")
    monkeypatch.setenv("RED_THREAD_AUTH_DEFAULT_YEAR", "")

    settings = Settings(_env_file=None)

    assert settings.resolved_data_dir == (PROJECT_ROOT / "data").resolve()
    assert settings.resolved_reports_dir == (PROJECT_ROOT / "reports").resolve()
    assert settings.resolved_database_url == (
        f"sqlite:///{PROJECT_ROOT / 'data' / 'red-thread.db'}"
    )
    assert settings.auth_default_year is None


def test_auth_default_year_parses(monkeypatch):
    monkeypatch.setenv("RED_THREAD_AUTH_DEFAULT_YEAR", "2026")

    settings = Settings(_env_file=None)

    assert settings.auth_default_year == 2026


def test_postgres_url_uses_psycopg_driver():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@host:5432/red-thread?sslmode=require",
    )
    assert settings.resolved_database_url == (
        "postgresql+psycopg://user:pass@host:5432/red-thread?sslmode=require"
    )


def test_postgres_short_scheme_uses_psycopg_driver():
    settings = Settings(
        _env_file=None,
        database_url="postgres://user:pass@host:5432/red-thread",
    )
    assert settings.resolved_database_url == (
        "postgresql+psycopg://user:pass@host:5432/red-thread"
    )


def test_r2_configuration_requires_credentials():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            storage_backend="r2",
            r2_account_id="account",
            r2_bucket="bucket",
        )


def test_r2_endpoint_is_derived_from_account():
    settings = Settings(
        _env_file=None,
        storage_backend="r2",
        r2_account_id="account",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="bucket",
    )
    assert settings.is_r2
    assert settings.resolved_r2_endpoint == "https://account.r2.cloudflarestorage.com"
