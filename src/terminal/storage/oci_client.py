import os
import tempfile
from typing import Optional

import ocifs

# Global instance for the filesystem
_fs_instance: Optional[ocifs.OCIFileSystem] = None


def _setup_oci_config() -> Optional[str]:
    """
    Sets up OCI configuration files from environment variables.
    Returns the path to the configuration file.
    """
    oci_config = os.environ.get("OCI_CONFIG")
    oci_key_content = os.environ.get("OCI_KEY")

    if not oci_config or not oci_key_content:
        return None

    # Create a temporary directory to store credentials
    temp_dir = tempfile.mkdtemp(prefix="oci_config_")

    key_path = os.path.join(temp_dir, "key.pem")
    config_path = os.path.join(temp_dir, "config")

    with open(key_path, "w") as key_file:
        key_file.write(oci_key_content)

    # OCI config needs to point to the key file
    config_content = oci_config + f"\nkey_file={key_path}\n"

    with open(config_path, "w") as config_file:
        config_file.write(config_content)

    return config_path


def get_fs() -> ocifs.OCIFileSystem:
    """
    Returns the initialized OCIFileSystem object.
    """
    global _fs_instance
    if _fs_instance is None:
        config_path = _setup_oci_config()
        if config_path:
            _fs_instance = ocifs.OCIFileSystem(config=config_path)
        else:
            bucket_name = os.environ.get("OCI_BUCKET")
            if not bucket_name:
                print(
                    "Warning: OCI environment variables (OCI_CONFIG, OCI_KEY, OCI_BUCKET) are missing."
                )
            else:
                # If we have a bucket but no config, it might be using default OCI auth or fail later
                pass
    return _fs_instance
