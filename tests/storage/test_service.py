import os
import pytest
from terminal.storage.fs import _setup_oci_config


def test_oci_client_setup():
    """
    Test that OCI configuration correctly creates temporary credentials.
    """
    config = "[DEFAULT]\nuser=test-user\ntenancy=test-tenancy\nfingerprint=test-fingerprint\nregion=test-region"
    key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCxKtYHYtUdoiRs\n-----END PRIVATE KEY-----"

    # Trigger internal setup
    config_path = _setup_oci_config(oci_config=config, oci_key=key)

    assert os.path.exists(config_path)
    with open(config_path, "r") as f:
        content = f.read()
        assert "user=test-user" in content
        assert "key_file=" in content

    # Clean up (usually handled by OS temp dir, but good to check it exists)
    temp_dir = os.path.dirname(config_path)
    assert os.path.exists(os.path.join(temp_dir, "key.pem"))
