import httpx
from typing import Literal, Union
from pydantic import BaseModel

# --- Constants ---
DEFAULT_HEADERS = {
    "accept": "application/json",
    "origin": "https://stocktwits.com",
    "referer": "https://stocktwits.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


# --- Parameter Models ---
class GlobalFeedParam(BaseModel):
    feed: Literal["trending", "suggested", "popular"]
    limit: int


class SymbolFeedParam(BaseModel):
    feed: Literal["symbol"]
    filter: Literal["trending", "popular"]
    symbol: str
    limit: int


Param = Union[GlobalFeedParam, SymbolFeedParam]


# --- StockTwits Client Class ---
class StockTwitsClient:
    def __init__(self):
        self.client = httpx.AsyncClient(headers=DEFAULT_HEADERS)

    async def fetch(self, params: Param) -> dict:
        url, query = self._to_request_param(params)
        response = await self.client.get(url, params=query)
        response.raise_for_status()
        return response.json()

    def _to_request_param(self, params: Param) -> tuple[str, dict]:
        if isinstance(params, SymbolFeedParam):
            parts = params.symbol.split(":")
            stocktwit_symbol = f"{parts[0]}.NSE" if len(parts) == 1 else f"{parts[1]}.{parts[0]}"

            if params.filter == "trending":
                url = f"https://api.stocktwits.com/api/2/streams/symbol/{stocktwit_symbol}.json"
                q = {"filter": "all", "limit": params.limit}
                return url, q
            else:  # filter == "popular"
                url = f"https://api.stocktwits.com/api/2/trending_messages/symbol/{stocktwit_symbol}.json"
                q = {"filter": "top", "limit": params.limit}
                return url, q

        if params.feed == "suggested":
            return (
                "https://api.stocktwits.com/api/2/streams/suggested.json",
                {"filter": "top", "limit": params.limit},
            )
        elif params.feed == "trending":
            return (
                "https://api.stocktwits.com/api/2/streams/trending.json",
                {"filter": "all", "limit": params.limit},
            )
        elif params.feed == "popular":
            return (
                "https://api.stocktwits.com/api/2/trending_messages/symbol_trending",
                {"filter": "all", "limit": params.limit},
            )

        raise ValueError(f"Invalid feed param: {params}")

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
