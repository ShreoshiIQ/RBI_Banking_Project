
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    jwt_secret_key: SecretStr | None = None
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    # Requires migration d190f0030001 and a non-owner API database role.
    tenant_isolation_enabled: bool = False
    # Optional OIDC single sign-on; local login keeps working alongside it.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_username_claim: str = "preferred_username"
    # Directory holding data/ and eval_gates.json for the insights API.
    data_root: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
