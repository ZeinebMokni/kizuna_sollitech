"""Application settings, loaded from environment variables (prefix QATRA_)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_MARKERS = ("change-me", "changeme", "secret")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QATRA_", env_file=(".env", "../.env"), extra="ignore"
    )

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://qatra:qatra@localhost:5433/qatra"

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cookie_secure: bool = False

    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    engine_url: str = "http://127.0.0.1:8100"
    mqtt_enabled: bool = Field(default=False, validation_alias="QATRA_MQTT_ENABLED")
    mqtt_host: str = Field(default="127.0.0.1", validation_alias="QATRA_MQTT_HOST")
    mqtt_port: int = Field(default=1883, validation_alias="QATRA_MQTT_PORT")
    mqtt_topic: str = Field(
        default="qatra/+/+/measurements/+",
        validation_alias="QATRA_MQTT_TOPIC",
    )
    actuation_max_duration_s: int = Field(
        default=2700,
        validation_alias="QATRA_ACTUATION_MAX_DURATION_S",
    )
    actuation_max_volume_m3: float = Field(
        default=100.0,
        validation_alias="QATRA_ACTUATION_MAX_VOLUME_M3",
    )

    login_max_failures: int = 5
    login_window_seconds: int = 900

    seed_demo_password: SecretStr | None = None

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < 32:
            raise ValueError("QATRA_JWT_SECRET must be at least 32 characters")
        if self.env == "production":
            if any(m in secret.lower() for m in _INSECURE_SECRET_MARKERS):
                raise ValueError("QATRA_JWT_SECRET looks like a placeholder")
            if not self.cookie_secure:
                raise ValueError("QATRA_COOKIE_SECURE must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
