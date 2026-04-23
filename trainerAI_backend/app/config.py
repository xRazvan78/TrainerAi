from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="", validation_alias="POSTGRES_DB")

    model_config = SettingsConfigDict(
        env_file=(".env"),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def derive_database_url(self):
        if self.database_url:
            return self

        self.database_url = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        return self

    def resolved_database_url(self) -> str:
        return self.database_url or ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
