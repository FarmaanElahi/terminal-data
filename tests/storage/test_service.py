import os
import pytest
from terminal.storage.service import OCIClient
import ocifs


def test_oci_client_setup():
    """
    Test that OCIClient correctly creates temporary credentials.
    """
    config = "[DEFAULT]\nuser=test-user\ntenancy=test-tenancy\nfingerprint=test-fingerprint\nregion=test-region"
    key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCxKtYHYtUdoiRs\n-----END PRIVATE KEY-----"

    client = OCIClient(oci_config=config, oci_key=key)

    # Trigger internal setup
    config_path = client._setup_oci_config()

    assert os.path.exists(config_path)
    with open(config_path, "r") as f:
        content = f.read()
        assert "user=test-user" in content
        assert "key_file=" in content

    # Clean up (usually handled by OS temp dir, but good to check it exists)
    temp_dir = os.path.dirname(config_path)
    assert os.path.exists(os.path.join(temp_dir, "key.pem"))


def test_oci_client_get_fs(monkeypatch):
    """
    Smoke test for OCIClient.get_fs.
    """
    config = "[DEFAULT]\nuser=test-user"
    key = "dummy-key"
    client = OCIClient(oci_config=config, oci_key=key)

    # We mock ocifs.OCIFileSystem to avoids actual OCI calls
    with pytest.MonkeyPatch().context() as m:
        m.setattr(ocifs, "OCIFileSystem", lambda **kwargs: "mock-fs")
        fs = client.get_fs()
        assert fs == "mock-fs"

        # Verify singleton behavior within the OCIClient instance
        assert client.get_fs() == "mock-fs"
