from pydantic_settings import BaseSettings, SettingsConfigDict
from terminal.enums import LogLevels


class Settings(BaseSettings):
    """
    Application settings managed by Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str

    # OCI Storage
    oci_bucket: str
    oci_config: str
    oci_key: str

    # logging
    log_level: LogLevels = LogLevels.debug

    @property
    def is_oci_configured(self) -> bool:
        return all([self.oci_config, self.oci_key, self.oci_bucket])


# Settings instance will be created here
settings = Settings()
