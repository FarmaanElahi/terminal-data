from modules.ezscan.core.scanner_engine import ScannerEngine
from modules.ezscan.providers.local_metadata_provider import LocalMetadataProvider
from modules.ezscan.providers.yahoo_candle_provider import YahooCandleProvider


def create_scanner_engine() -> ScannerEngine:
    # Initialize data providers
    candle_provider = YahooCandleProvider(
        cache_file="ohlcv_separated.pkl",
        period="10y"
    )
    metadata_provider = LocalMetadataProvider()

    return ScannerEngine(
        candle_provider=candle_provider,
        metadata_provider=metadata_provider,
        cache_enabled=False,
    )
