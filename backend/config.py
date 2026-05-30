from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Books Czar"
    data_dir: Path = Field(
        default=Path("./data"),
        validation_alias=AliasChoices("BOOKWISE_DATA_DIR", "DATA_DIR"),
    )
    books_dir: Path = Field(
        default=Path("./books"),
        validation_alias=AliasChoices("BOOKWISE_BOOKS_DIR", "BOOKS_DIR"),
    )
    lmstudio_base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        validation_alias=AliasChoices("LMSTUDIO_BASE_URL", "BOOKWISE_LMSTUDIO_BASE_URL"),
    )
    lmstudio_chat_model: str = Field(
        default="local-model",
        validation_alias=AliasChoices("LMSTUDIO_CHAT_MODEL", "BOOKWISE_LMSTUDIO_CHAT_MODEL"),
    )
    lmstudio_embedding_model: str = Field(
        default="text-embedding-nomic-embed-text-v1.5",
        validation_alias=AliasChoices("LMSTUDIO_EMBEDDING_MODEL", "BOOKWISE_LMSTUDIO_EMBEDDING_MODEL"),
    )
    max_download_mb: int = Field(
        default=250,
        validation_alias=AliasChoices("BOOKWISE_MAX_DOWNLOAD_MB", "MAX_DOWNLOAD_MB"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "books_czar.sqlite3"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    settings.books_dir.mkdir(parents=True, exist_ok=True)
    legacy_database_path = settings.data_dir / "bookwise.sqlite3"
    if legacy_database_path.exists() and not settings.database_path.exists():
        legacy_database_path.replace(settings.database_path)
    return settings
