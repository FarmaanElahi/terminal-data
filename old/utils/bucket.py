import os
import ocifs

_oci_config = os.environ.get("OCI_CONFIG")
_oci_key_content = os.environ.get("OCI_KEY")
data_bucket = os.environ.get("OCI_BUCKET")

OCI_PRIVATE_KEY_PATH = "./key.pem"
OCI_CONFIG_PATH = "./config"

if os.path.exists(os.path.relpath(OCI_PRIVATE_KEY_PATH)):
    with open(os.path.relpath(OCI_PRIVATE_KEY_PATH), 'r') as f:
        _oci_key_content = f.read()
    with open(os.path.relpath(OCI_CONFIG_PATH), 'r') as f:
        _oci_config = f.read()
else:
    if _oci_config is None or _oci_key_content is None or data_bucket is None:
        raise KeyError("Missing OCI config")
    with open(OCI_PRIVATE_KEY_PATH, "w") as key_file:
        key_file.write(_oci_key_content)
        OCI_PRIVATE_KEY_PATH = key_file.name  # Full URL

    with open(OCI_CONFIG_PATH, "w") as config_file:
        _oci_config += f'\nkey_file={OCI_PRIVATE_KEY_PATH}'
        config_file.write(_oci_config)
        OCI_CONFIG_PATH = config_file.name

storage_options = {"config": OCI_CONFIG_PATH}
data_bucket_fs = ocifs.OCIFileSystem(OCI_CONFIG_PATH)
print("OCI FS Configured")
