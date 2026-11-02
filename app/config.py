from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str
    openai_model: str = "gpt-5.4"

    caldav_url: str = "https://caldav.icloud.com/"
    caldav_username: str
    caldav_password: str
    caldav_calendar: str

    timezone: str = "America/Denver"
    app_passcode: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("app_passcode")
    @classmethod
    def _blank_passcode_is_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
