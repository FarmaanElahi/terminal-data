from fsspec.spec import AbstractFileSystem

from modules.ezscan.core.scanner_engine import ScannerEngine


def create_scanner_engine(fs: AbstractFileSystem) -> ScannerEngine:
    return ScannerEngine(fs, cache_enabled=False)
