import json
from external.tradingview import TradingViewScreenerClient
from core.storage import get_fs
import os


async def sync_symbols():
    """
    Syncs symbols from TradingView and stores them in OCI S3.
    """
    client = TradingViewScreenerClient()
    symbols = await client.fetch_symbols()

    # Store as symbols/symbols.json in the bucket
    bucket = os.environ.get("OCI_BUCKET")
    if not bucket:
        raise ValueError("OCI_BUCKET environment variable is not set")

    fs = get_fs()
    file_path = f"{bucket}/symbols/symbols.json"

    # Ensure directory exists (ocifs handles it usually, but let's be safe)
    # Actually ocifs doesn't need explicit mkdir for S3-like paths

    with fs.open(file_path, "w") as f:
        json.dump(symbols, f)

    return len(symbols)
