from itertools import batched
from typing import Any, Literal
import httpx
from modules.core.provider.upstox.utils import to_upstox_instrument_key, from_upstox_instrument_key


async def fetch_quotes(symbols: list[dict[str, Any]], token: str):
    for batch in list(batched(symbols, 500)):
        yield await fetch_ohlc_data([*batch], "1d", token)


async def fetch_ohlc_data(symbols: list[dict[str, Any]], interval: Literal["1d"], token: str):
    url = "https://api.upstox.com/v2/market-quote/quotes"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    instrument_keys = [to_upstox_instrument_key(s) for s in symbols if to_upstox_instrument_key(s) is not None]
    params = {
        "instrument_key": ",".join(instrument_keys),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        data = result.get("data", {})
        r = [extrac_quote(v) for v in data.values()]
        return r


def extrac_quote(quote: dict[str, Any]):
    o = quote.get("ohlc", {}).get("open")
    h = quote.get("ohlc", {}).get("high")
    l = quote.get("ohlc", {}).get("low")
    c = quote.get("ohlc", {}).get("close")
    v = quote.get("volume")
    ch = quote.get('net_change')
    lp = quote.get('last_price')
    pc = lp - ch

    quote = dict(
        ticker=from_upstox_instrument_key(quote.get("instrument_token")),
    )
    if o is not None:
        quote["day_open"] = o
    if h is not None:
        quote["day_high"] = h
    if l is not None:
        quote["day_low"] = l
    if c is not None:
        quote["day_close"] = c
    if c is not None and pc is not None:
        quote["price_change_today_pct"] = (c - pc) / pc * 100
    if o is not None and h is not None and l is not None and c is not None:
        quote["dcr"] = (c - l) / (h - l) * 100
    if o is not None and c is not None:
        quote['price_change_from_open_abs'] = c - o
        quote['price_change_from_open_pct'] = (c - o) / o * 100
    if h is not None and c is not None:
        quote['price_change_from_high_abs'] = h - c
        quote['price_change_from_high_pct'] = (h - c) / h * 100
    if o is not None and pc is not None:
        quote['gap_dollar_D'] = o - pc
        quote['gap_pct_D'] = (o - pc) / pc * 100

    return quote
