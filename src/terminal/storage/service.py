import os
import tempfile
import ocifs


class OCIClient:
    """
    Manages OCI FileSystem lifecycle without global state.
    """

    def __init__(self, oci_config: str, oci_key: str):
        self.oci_config = oci_config
        self.oci_key = oci_key
        self._fs: ocifs.OCIFileSystem | None = None

    def _setup_oci_config(self) -> str:
        """
        Sets up OCI configuration files from provided strings.
        Returns the path to the temporary configuration file.
        """

        def clean_val(val: str) -> str:
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            return val.encode().decode("unicode_escape").strip()

        config_content = clean_val(self.oci_config)
        key_content = clean_val(self.oci_key)

        # Create a temporary directory to store credentials
        temp_dir = tempfile.mkdtemp(prefix="oci_config_")

        key_path = os.path.join(temp_dir, "key.pem")
        config_path = os.path.join(temp_dir, "config")

        with open(key_path, "w") as key_file:
            key_file.write(key_content)

        # OCI config needs to point to the key file
        final_config_content = config_content + f"\nkey_file={key_path}\n"

        with open(config_path, "w") as config_file:
            config_file.write(final_config_content)

        return config_path

    def get_fs(self) -> ocifs.OCIFileSystem:
        """
        Returns an initialized OCIFileSystem object.
        """
        if self._fs is None:
            config_path = self._setup_oci_config()
            self._fs = ocifs.OCIFileSystem(config=config_path)
        return self._fs
