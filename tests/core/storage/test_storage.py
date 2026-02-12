import os
from core.storage import get_fs


def test_storage_ls():
    """
    Test that get_fs() returns a filesystem object and can list the bucket.
    """
    fs = get_fs()
    assert fs is not None, "get_fs() should return a filesystem object"

    bucket = os.environ.get("OCI_BUCKET")
    assert bucket is not None, "OCI_BUCKET env var must be set for testing"

    # Simple ls should run without error
    try:
        files = fs.ls(bucket)
        assert isinstance(files, list)
        print(f"Found {len(files)} files in {bucket}")
    except Exception as e:
        assert False, f"fs.ls({bucket}) failed with error: {e}"
