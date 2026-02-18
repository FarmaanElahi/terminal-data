from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from terminal.enums import LogLevels

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

    # logging
    log_level: LogLevels = LogLevels.info

    @property
    def is_oci_configured(self) -> bool:
        return all([self.oci_config, self.oci_key, self.oci_bucket])


# Settings instance will be created here
settings = Settings()
