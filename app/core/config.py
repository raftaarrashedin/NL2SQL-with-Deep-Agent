from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NL2SQL Deep Agent API"
    app_version: str = "0.2.0"
    database_url: str = Field(default="sqlite:///./nl2sql.db", alias="DATABASE_URL")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="password", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="nl2sql_app", alias="POSTGRES_DB")
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    huggingfacehub_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_API_KEY"),
    )
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")

    default_llm_provider: str = Field(default="openai", alias="DEFAULT_LLM_PROVIDER")
    default_model: str = Field(default="gpt-4o", alias="DEFAULT_MODEL")
    default_sql_model: str | None = Field(default=None, alias="DEFAULT_SQL_MODEL")

    max_chat_history_messages: int = Field(default=24, alias="MAX_CHAT_HISTORY_MESSAGES")
    max_sql_execution_attempts: int = Field(default=2, alias="MAX_SQL_EXECUTION_ATTEMPTS")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url and "${" not in self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
