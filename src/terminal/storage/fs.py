import os
import tempfile
import ocifs
import logging
from fsspec import AbstractFileSystem
from terminal.config import settings

logger = logging.getLogger(__name__)


def _setup_oci_config(oci_config: str, oci_key: str) -> str:
    """
    Sets up OCI configuration files from provided strings.
    Returns the path to the temporary configuration file.
    """
    config_content = oci_config.strip()
    key_content = oci_key.strip()

    temp_dir = tempfile.mkdtemp(prefix="oci_config_")
    key_path = os.path.join(temp_dir, "key.pem")
    config_path = os.path.join(temp_dir, "config")

    with open(key_path, "w") as key_file:
        key_file.write(key_content)

    final_config_content = config_content + f"\nkey_file={key_path}\n"

    with open(config_path, "w") as config_file:
        config_file.write(final_config_content)

    return config_path


# Global instance initialized at import time
fs: AbstractFileSystem = ocifs.OCIFileSystem(
    config=_setup_oci_config(settings.oci_config, settings.oci_key)
)
