from app.config import Settings


ENV_KEYS = (
    "DATABASE_URL",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)


def _clear_env(monkeypatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_settings_port_defaults_5432(monkeypatch) -> None:
    _clear_env(monkeypatch)
    settings = Settings()

    assert settings.postgres_port == 5432


def test_settings_database_url_prefers_explicit_value(monkeypatch) -> None:
    _clear_env(monkeypatch)

    monkeypatch.setenv("POSTGRES_HOST", "from_parts_host")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "from_parts_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "from_parts_password")
    monkeypatch.setenv("POSTGRES_DB", "from_parts_db")

    explicit_url = "postgresql+asyncpg://explicit_user:explicit_pass@explicit_host:5432/explicit_db"
    monkeypatch.setenv("DATABASE_URL", explicit_url)

    settings = Settings()

    assert settings.resolved_database_url() == explicit_url


def test_settings_derives_database_url_from_parts(monkeypatch) -> None:
    _clear_env(monkeypatch)

    monkeypatch.setenv("POSTGRES_HOST", "db_host")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "db_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db_password")
    monkeypatch.setenv("POSTGRES_DB", "db_name")

    settings = Settings()
    expected = "postgresql+asyncpg://db_user:db_password@db_host:5432/db_name"

    assert settings.database_url == expected
    assert settings.resolved_database_url() == expected
