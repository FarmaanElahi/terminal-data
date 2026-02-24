import httpx
import json
from typing import Any


class TradingViewScanner:
    """
    Client for interacting with TradingView Scanner API to fetch symbols.
    """

    SCANNER_URL = "https://tv-scanner.devfarmaan.workers.dev/global/scan?label-product=popup-screener-stock"

    DEFAULT_HEADERS = {
        "accept": "application/json",
        "content-type": "text/plain;charset=UTF-8",
        "origin": "https://in.tradingview.com",
        "referer": "https://in.tradingview.com/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    }

    async def fetch_symbols(
        self, markets: list[str] = ["india"]
    ) -> list[dict[str, Any]]:
        """
        Fetches symbols from TradingView for the specified markets.
        """
        all_symbols = []

        async with httpx.AsyncClient() as client:
            for market in markets:
                payload = {
                    "columns": [
                        "name",
                        "logoid",
                        "is_primary",
                        "isin",
                        "exchange",
                        "country",
                        "type",
                        "typespecs",
                        "indexes",
                    ],
                    "filter": [
                        {
                            "left": "is_primary",
                            "operation": "equal",
                            "right": True,
                        },
                        {
                            "left": "exchange",
                            "operation": "in_range",
                            "right": ["NSE", "BSE"],
                        },
                    ],
                    "filter2": {
                        "operator": "and",
                        "operands": [
                            {
                                "operation": {
                                    "operator": "or",
                                    "operands": [
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "stock",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["common"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "stock",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["preferred"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "dr",
                                                        }
                                                    }
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "fund",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["etf"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                    ],
                                }
                            },
                            {
                                "expression": {
                                    "left": "typespecs",
                                    "operation": "has_none_of",
                                    "right": ["pre-ipo"],
                                }
                            },
                        ],
                    },
                    "ignore_unknown_fields": False,
                    "options": {"lang": "en"},
                    "range": [],
                    "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
                    "symbols": {},
                    "markets": [market],
                }

                response = await client.post(
                    self.SCANNER_URL,
                    headers=self.DEFAULT_HEADERS,
                    content=json.dumps(payload),
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get("data", []):
                    # item format: {"s": "TICKER", "d": [values in columns order]}
                    ticker = item["s"]
                    details = item["d"]
                    raw_type = details[6]
                    raw_specs = details[7] or []

                    symbol_info = {
                        "ticker": ticker,
                        "name": details[0],
                        "logo": details[1],
                        "is_primary": details[2],
                        "isin": details[3],
                        "exchange": details[4],
                        "country": details[5],
                        "market": market,
                        "type": raw_type,
                        "typespecs": raw_specs,
                        "indexes": details[8] if details[8] else [],
                    }
                    all_symbols.append(symbol_info)

            return all_symbols

    async def fetch_ohlcv(
        self, markets: list[str] = ["india"]
    ) -> dict[str, tuple[int, float, float, float, float, float]]:
        """
        Fetches daily OHLCV data for all symbols from TradingView Scanner API.
        Returns a dict of {ticker: (timestamp, open, high, low, close, volume)}.
        """
        result: dict[str, tuple[int, float, float, float, float, float]] = {}

        async with httpx.AsyncClient() as client:
            for market in markets:
                payload = {
                    "columns": [
                        "daily-bar.time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                    ],
                    "filter": [
                        {
                            "left": "is_primary",
                            "operation": "equal",
                            "right": True,
                        },
                        {
                            "left": "exchange",
                            "operation": "in_range",
                            "right": ["NSE", "BSE"],
                        },
                    ],
                    "filter2": {
                        "operator": "and",
                        "operands": [
                            {
                                "operation": {
                                    "operator": "or",
                                    "operands": [
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "stock",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["common"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "stock",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["preferred"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "dr",
                                                        }
                                                    }
                                                ],
                                            }
                                        },
                                        {
                                            "operation": {
                                                "operator": "and",
                                                "operands": [
                                                    {
                                                        "expression": {
                                                            "left": "type",
                                                            "operation": "equal",
                                                            "right": "fund",
                                                        }
                                                    },
                                                    {
                                                        "expression": {
                                                            "left": "typespecs",
                                                            "operation": "has",
                                                            "right": ["etf"],
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                    ],
                                }
                            },
                            {
                                "expression": {
                                    "left": "typespecs",
                                    "operation": "has_none_of",
                                    "right": ["pre-ipo"],
                                }
                            },
                        ],
                    },
                    "ignore_unknown_fields": False,
                    "options": {"lang": "en"},
                    "range": [],
                    "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
                    "symbols": {},
                    "markets": [market],
                }

                response = await client.post(
                    self.SCANNER_URL,
                    headers=self.DEFAULT_HEADERS,
                    content=json.dumps(payload),
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get("data", []):
                    ticker = item["s"]
                    details = item["d"]
                    # columns: daily-bar.time, open, high, low, close, volume
                    timestamp = details[0]
                    open_p = details[1]
                    high_p = details[2]
                    low_p = details[3]
                    close_p = details[4]
                    volume_p = details[5]

                    if timestamp is None or close_p is None:
                        continue

                    result[ticker] = (
                        int(timestamp),
                        float(open_p or 0),
                        float(high_p or 0),
                        float(low_p or 0),
                        float(close_p or 0),
                        float(volume_p or 0),
                    )

        return result
