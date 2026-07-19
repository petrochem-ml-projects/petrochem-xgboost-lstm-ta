"""Unit test for the root setting configuration class"""

from __future__ import annotations

import pytest

from config import Settings

pytestmark = pytest.mark.unit

_POSTGRES_ENV_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "MLFLOW_TRACKING_URI",
]


def make_settings() -> Settings:
    """Construct Settings without reading any local .env file."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all Settings-related variables from environment"""
    for var in _POSTGRES_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults() -> None:
    """With no env vars and no .env file, the local-dev defaults apply"""
    settings = make_settings()
    assert settings.postgres_host == "localhost"
    assert settings.postgres_port == 5432
    assert settings.postgres_db == "petrochem"
    assert settings.postgres_user == "petrochem"
    assert settings.postgres_password == "petrochem"
    assert settings.mlflow_tracking_uri == "http://localhost:5000"


def test_database_url_composition() -> None:
    """database_url assembles the exact SQLAlchemy URL from the fields."""
    settings = make_settings()
    assert (
        settings.database_url
        == "postgresql+psycopg2://petrochem:petrochem@localhost:5432/petrochem"
    )


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real environment variable beats the coded default"""
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    settings = make_settings()
    assert settings.postgres_password == "s3cret"
    assert settings.postgres_port == 6543
    assert (
        settings.database_url == "postgresql+psycopg2://petrochem:s3cret@localhost:6543/petrochem"
    )


# Write a new test that sets only the database name via the environment.
# Check that all other defaults stay the same, but the database name is updated.
def test_db_name_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_DB", "pritamdb")
    settings = make_settings()
    assert settings.postgres_db == "pritamdb"
