import asyncio
from cloudscraper import CloudScraper, create_scraper
from urllib.parse import urlencode

from .models import SymbolFeedParam, Param


class StockTwitsClient:
    """
    Client for interacting with StockTwits API to fetch ideas/feeds.
    """

    def __init__(self):
        self.scraper: CloudScraper = create_scraper()

    async def fetch(self, params: Param) -> dict:
        """
        Fetches feed from StockTwits based on parameters.
        """
        url, query = self._to_request_param(params)
        query_string = urlencode(query)
        full_url = f"{url}?{query_string}"

        # Cloudscraper is synchronous, so we run it in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.scraper.get(full_url))

        response.raise_for_status()
        return response.json()

    def _to_request_param(self, params: Param) -> tuple[str, dict]:
        if isinstance(params, SymbolFeedParam):
            parts = params.symbol.split(":")
            # Map to StockTwits format:
            # - NSE/BSE: ticker.EXCHANGE (e.g. NSE:RELIANCE -> RELIANCE.NSE)
            # - Others: ticker (e.g. NASDAQ:AAPL -> AAPL)
            if len(parts) == 2:
                exchange = parts[0].upper()
                ticker = parts[1]
                if exchange in ["NSE", "BSE"]:
                    stocktwit_symbol = f"{ticker}.{exchange}"
                else:
                    stocktwit_symbol = ticker
            else:
                stocktwit_symbol = parts[0]

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
        # CloudScraper doesn't strictly have an async close, but we provide it for consistency
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
