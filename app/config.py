from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"

    @field_validator("log_level", mode="before")
    @classmethod
    def upper_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("log_format", mode="before")
    @classmethod
    def lower_log_format(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


settings = Settings()
