import httpx
import json
from typing import Any, Dict, List


class TradingViewScreenerClient:
    """
    Client for interacting with TradingView Scanner API to fetch symbols.
    """

    SCANNER_URL = (
        "https://scanner.tradingview.com/global/scan?label-product=popup-screener-stock"
    )

    DEFAULT_HEADERS = {
        "accept": "application/json",
        "content-type": "text/plain;charset=UTF-8",
        "origin": "https://in.tradingview.com",
        "referer": "https://in.tradingview.com/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    }

    async def fetch_symbols(
        self, markets: List[str] = ["india", "america"]
    ) -> List[Dict[str, Any]]:
        """
        Fetches symbols from TradingView for the specified markets.
        """
        payload = {
            "columns": [
                "name",
                "logoid",
                "is_primary",
                "isin",
                "exchange",
                "country",
                "typespecs",
                "indexes",
            ],
            "filter": [{"left": "is_primary", "operation": "equal", "right": True}],
            "ignore_unknown_fields": False,
            "options": {"lang": "en"},
            "range": [],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "symbols": {},
            "markets": markets,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.SCANNER_URL,
                headers=self.DEFAULT_HEADERS,
                data=json.dumps(payload),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            symbols = []
            for item in data.get("data", []):
                # item format: {"s": "TICKER", "d": [values in columns order]}
                ticker = item["s"]
                details = item["d"]
                symbol_info = {
                    "ticker": ticker,
                    "name": details[0],
                    "logo": details[1],
                    "is_primary": details[2],
                    "isin": details[3],
                    "exchange": details[4],
                    "country": details[5],
                    "type": details[6][0] if details[6] else None,
                    "indexes": [idx["name"] for idx in details[7]]
                    if details[7]
                    else [],
                }
                symbols.append(symbol_info)

            return symbols
