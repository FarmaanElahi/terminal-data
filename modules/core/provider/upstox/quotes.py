from itertools import batched
from typing import Any, Literal
import httpx
from modules.core.provider.upstox.utils import to_upstox_instrument_key, from_upstox_instrument_key


async def fetch_quotes(symbols: list[dict[str, Any]], token: str):
    for batch in list(batched(symbols, 500)):
        yield await fetch_ohlc_data([*batch], "1d", token)


async def fetch_ohlc_data(symbols: list[dict[str, Any]], interval: Literal["1d"], token: str):
    url = "https://api.upstox.com/v3/market-quote/ohlc"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    instrument_keys = [to_upstox_instrument_key(s) for s in symbols if to_upstox_instrument_key(s) is not None]
    params = {
        "instrument_key": ",".join(instrument_keys),
        "interval": interval
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        data = result.get("data", {})
        r = [
            {
                "ticker": from_upstox_instrument_key(v.get("instrument_token")),
                "prev_ohlc": v.get("prev_ohlc"),
                "live_ohlc": v.get("live_ohlc"),
                "lp": v.get("last_price")
            } for v in data.values()
        ]
        return r
