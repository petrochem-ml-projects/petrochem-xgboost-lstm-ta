"""Application settings loaded from the environment (see .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for Postgres and MLflow.

    Values are resolved in precedence order: real environment variables,
    then a local ``.env`` file, then the local-dev defaults below.

    Example:
        >>> settings = Settings()
        >>> settings.database_url
        'postgresql+psycopg2://petrochem:petrochem@localhost:5432/petrochem'
    """

    model_config = SettingsConfigDict(env_file=".env")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "petrochem"
    postgres_user: str = "petrochem"
    postgres_password: str = "petrochem"
    mlflow_tracking_uri: str = "http://localhost:5000"

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL assembled from the Postgres fields."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


class _DocsCheckProbe:
    def _a(self) -> None:
        pass

    def _b(self) -> None:
        pass

    def _c(self) -> None:
        pass

    def _d(self) -> None:
        pass

    def _e(self) -> None:
        pass

    def _f(self) -> None:
        pass
