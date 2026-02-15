import httpx
import json
from typing import Any


class TradingViewScanner:
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
        self, markets: list[str] = ["india", "america"]
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
                        "indexes": [idx["name"] for idx in details[8]]
                        if details[8]
                        else [],
                    }
                    all_symbols.append(symbol_info)

            return all_symbols

    async def fetch_ohlc(
        self, markets: list[str] = ["india", "america"]
    ) -> list[dict[str, Any]]:
        """
        Fetches the latest OHLC data for symbols in the specified markets.
        """
        all_ohlc = []
        payload_base = {
            "columns": [
                "daily-bar.time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
            "filter": [
                {"left": "is_primary", "operation": "equal", "right": True},
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
                                                    "right": "stock",
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
        }

        async with httpx.AsyncClient() as client:
            for market in markets:
                payload = payload_base.copy()
                payload["markets"] = [market]

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
                    d = item["d"]
                    all_ohlc.append(
                        {
                            "ticker": ticker,
                            "timestamp": int(d[0]),  # daily-bar.time
                            "open": d[1],
                            "high": d[2],
                            "low": d[3],
                            "close": d[4],
                            "volume": d[5],
                        }
                    )

        return all_ohlc
