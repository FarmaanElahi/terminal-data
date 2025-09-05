from modules.ezscan.core.scanner_engine import ScannerEngine
from modules.ezscan.providers.yahoo_candle_provider import YahooCandleProvider


def create_scanner_engine() -> ScannerEngine:
    return ScannerEngine(cache_enabled=False)
