from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def is_oci_configured(self) -> bool:
        return all([self.oci_config, self.oci_key, self.oci_bucket])


# Settings instance will be created via FastAPI dependency injection
# No global settings instance here to avoid direct project-wide access
