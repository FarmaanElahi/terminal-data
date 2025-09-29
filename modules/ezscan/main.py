from typing import Literal

from modules.ezscan.core.scanner_engine import ScannerEngine
from utils.bucket import data_bucket_fs


def refresh_candles(market: Literal["india", "us"] | None = None):
    scanner = ScannerEngine(data_bucket_fs, auto_load=False, cache_enabled=False)
    scanner.refresh_data(market)
