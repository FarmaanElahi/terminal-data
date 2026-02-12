import httpx
from typing import Literal, Union
from pydantic import BaseModel
from cloudscraper import CloudScraper, create_scraper
from urllib.parse import urlencode

# --- Constants ---
DEFAULT_HEADERS = {
    "accept": "application/json",
    "accept-encoding": "gzip, deflate, br",
    "host": "api.stocktwits.com",
    "user-agent": "PostmanRuntime/7.44.1",
    "cache-control": "no-cache"
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
    client: CloudScraper

    def __init__(self):
        self.client = create_scraper()

    async def fetch(self, params: Param) -> dict:
        url, query = self._to_request_param(params)
        query_string = urlencode(query)
        full_url = f"{url}?{query_string}"
        response = self.client.get(full_url)
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
