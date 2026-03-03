import base64
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from terminal.enums import LogLevels
import os

# Resolve project root: config.py is at src/terminal/config.py → parents[2] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Application settings managed by Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str

    # OCI Storage
    oci_bucket: str
    oci_config: str
    oci_key: str

    @field_validator("oci_config", "oci_key", mode="before")
    @classmethod
    def decode_base64_credentials(cls, v: str) -> str:
        if v:
            try:
                # Attempt to parse as base64 string
                decoded_bytes = base64.b64decode(v, validate=True)
                return decoded_bytes.decode("utf-8")
            except Exception:
                # Fallback mechanism if the string is not actually base64
                return v.strip(" \"'")
        return v

    # logging
    log_level: LogLevels = LogLevels.info
    log_format: str = "text"  # "text" for human-readable, "json" for structured JSON

    # Environment
    environment: str = "development"  # development | staging | production

    # Upstox
    upstox_access_token: str = ""  # Deprecated — kept for backward compat during migration

    # Encryption key for DB secrets (generate: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    encryption_key: str = ""

    # Upstox OAuth2 credentials
    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_redirect_uri: str = ""  # e.g. "http://localhost:5173/broker/upstox/callback"

    @field_validator("encryption_key", mode="after")
    @classmethod
    def check_encryption_key(cls, v: str, info) -> str:
        env = info.data.get("environment", "development")
        if env == "production" and not v:
            raise ValueError("Must set ENCRYPTION_KEY in production environment")
        return v

    @property
    def is_upstox_oauth_configured(self) -> bool:
        return all([self.upstox_api_key, self.upstox_api_secret, self.upstox_redirect_uri])

    # Auth
    secret_key: str = "SUPER_SECRET_KEY_REPLACE_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    min_password_length: int = 8

    @field_validator("secret_key", mode="after")
    @classmethod
    def check_secret_key(cls, v: str, info) -> str:
        env = info.data.get("environment", "development")
        if env == "production" and v == "SUPER_SECRET_KEY_REPLACE_IN_PRODUCTION":
            raise ValueError("Must set SECRET_KEY in production environment")
        return v

    @property
    def is_oci_configured(self) -> bool:
        return all([self.oci_config, self.oci_key, self.oci_bucket])

    def abs_file_path(self, file_path: str) -> str:
        return os.path.join(self.oci_bucket, "v2", file_path)


# Settings instance will be created here
settings = Settings()
