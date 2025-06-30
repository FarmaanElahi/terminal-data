import asyncio
import datetime
from typing import Literal, Optional

import pandas as pd
from httpx import AsyncClient

from modules.core.provider.base.candles import CandleProvider

# Provided index mappings
MAPPINGS = {
    "NSE:BAJAJ_AUTO": "NSE_EQ|INE917I01010",
    "NSE:ELECTCAST": "NSE_EQ|INE086A01029",
    "BSE:SENSEX": "BSE_INDEX|SENSEX",
    "NSE:CNXENERGY": "NSE_INDEX|Nifty Energy",
    "NSE:NIFTY_INDIA_MFG": "NSE_INDEX|NIFTY INDIA MFG",
    "NSE:CNXINFRA": "NSE_INDEX|Nifty Infra",
    "NSE:CNXFMCG": "NSE_INDEX|Nifty FMCG",
    "NSE:CNXAUTO": "NSE_INDEX|Nifty Auto",
    "NSE:CNXIT": "NSE_INDEX|Nifty IT",
    "NSE:CNXFINANCE": "NSE_INDEX|Nifty Fin Service",
    "NSE:BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "NSE:CNX500": "NSE_INDEX|Nifty 500",
    "NSE:NIFTY": "NSE_INDEX|Nifty 50",
    "NSE:NIFTY_LARGEMID250": "NSE_INDEX|NIFTY LARGEMID250",
    "NSE:NIFTY_IND_DIGITAL": "NSE_INDEX|NIFTY IND DIGITAL",
    "NSE:CNXMNC": "NSE_INDEX|Nifty MNC",
    "NSE:CNXSERVICE": "NSE_INDEX|",
    "NSE:NIFTY_TOTAL_MKT": "NSE_INDEX|NIFTY TOTAL MKT",
    "NSE:CPSE": "NSE_INDEX|Nifty CPSE",
    "NSE:NIFTY_MICROCAP250": "NSE_INDEX|NIFTY MICROCAP250",
    "NSE:CNXCOMMODITIES": "NSE_INDEX|Nifty Commodities",
    "NSE:NIFTYALPHA50": "NSE_INDEX|NIFTY Alpha 50",
    "NSE:CNXCONSUMPTION": "NSE_INDEX|Nifty Consumption",
    "NSE:NIFTYMIDCAP150": "NSE_INDEX|NIFTY MIDCAP 150",
    "NSE:CNX100": "NSE_INDEX|Nifty 100",
    "NSE:NIFTYMIDSMAL400": "NSE_INDEX|",
    "NSE:CNXPSE": "NSE_INDEX|Nifty PSE",
    "NSE:NIFTYSMLCAP250": "NSE_INDEX|NIFTY SMLCAP 250",
    "NSE:NIFTYMIDCAP50": "NSE_INDEX|Nifty Midcap 50",
    "NSE:CNXMIDCAP": "NSE_INDEX|NIFTY MIDCAP 100",
    "NSE:CNXSMALLCAP": "NSE_INDEX|NIFTY SMLCAP 100",
    "NSE:NIFTY_MID_SELECT": "NSE_INDEX|NIFTY MID SELECT",
    "NSE:NIFTY_HEALTHCARE": "NSE_INDEX|NIFTY HEALTHCARE",
    "NSE:NIFTY_CONSR_DURL": "NSE_INDEX|NIFTY CONSR DURBL",
    "NSE:NIFTY_OIL_AND_GAS": "NSE_INDEX|NIFTY OIL AND GAS",
    "NSE:NIFTYPVTBANK": "NSE_INDEX|Nifty Pvt Bank",
    "NSE:CNXMEDIA": "NSE_INDEX|Nifty Media",
    "NSE:CNXREALTY": "NSE_INDEX|Nifty Realty",
    "NSE:CNX200": "NSE_INDEX|Nifty 200",
    "NSE:CNXMETAL": "NSE_INDEX|Nifty Metal",
    "NSE:CNXPSUBANK": "NSE_INDEX|Nifty PSU Bank",
    "NSE:CNXPHARMA": "NSE_INDEX|Nifty Pharma",
    "NSE:NIFTYJR": "NSE_INDEX|Nifty Next 50",
    "NSE:NIFTY_IND_DEFENCE": "NSE_INDEX|Nifty Ind Defence",
}


class UpstoxCandleProvider(CandleProvider):
    client: AsyncClient
    symbols: pd.DataFrame

    def __init__(self):
        super().__init__()
        self.client = AsyncClient(base_url="https://api.upstox.com/v3")

    async def prepare(self):
        url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
        df = pd.read_json(url, compression='gzip')
        self.symbols = df

    def get_instrument_key(self, symbol: str) -> Optional[str]:
        df = self.symbols
        # Try as index first
        key = MAPPINGS.get(symbol)
        if key:
            return key

        try:
            exchange, name = symbol.split(":")
            name = name.replace("_", "-")
        except ValueError:
            raise ValueError("Symbol format should be '<Exchange>:<Symbol Name>'")

        # Try as stock
        segment = f"{exchange}_EQ"
        match = df[
            (df.exchange == exchange)
            & (df.segment == segment)
            & (df.trading_symbol == name)
            ]
        if not match.empty:
            return match.iloc[0]["instrument_key"]

        raise ValueError(f"Could not resolve instrument key for symbol: {symbol}")

    async def candles(
            self,
            ticker: str,
            unit: Literal["minutes", "hours", "days", "weeks", "months"] = "days",
            interval: int = 1,
            to_date: datetime.date = datetime.date.today(),
            duration: datetime.timedelta = datetime.timedelta(days=365 * 5),
    ) -> pd.DataFrame:

        try:
            instrument_key = self.get_instrument_key(ticker)
        except ValueError:
            raise RuntimeError(f"Error getting instrument key  for {ticker}")

        from_date_str = (to_date - duration).strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")

        hist_url = f"/historical-candle/{instrument_key}/{unit}/{interval}/{to_date_str}/{from_date_str}"
        intraday_url = f"/historical-candle/intraday/{instrument_key}/{unit}/{interval}"

        async def fetch_hist():
            try:
                resp = await self.client.get(hist_url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                return resp.json()["data"]["candles"]
            except Exception as e:
                raise RuntimeError(f"Error fetching historical candles: {e}")

        async def fetch_intraday():
            try:
                resp = await self.client.get(intraday_url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                return resp.json()["data"]["candles"]
            except Exception as e:
                raise RuntimeError(f"Error fetching intraday candles: {e}")

        # Run both requests concurrently
        hist_candles, intraday_candles = await asyncio.gather(fetch_hist(), fetch_intraday())

        df_hist = pd.DataFrame(hist_candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
        df_hist.sort_values("timestamp", inplace=True,ascending=True)
        df_intra = pd.DataFrame(intraday_candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])

        if not df_intra.empty and not df_hist.empty:
            df_combined = pd.concat([df_hist, df_intra])
        elif not df_hist.empty:
            df_combined = df_hist
        else:
            df_combined = df_intra

        if unit in ['days', 'weeks', 'months']:
            df_combined["timestamp"] = pd.to_datetime(df_combined["timestamp"]).dt.tz_localize(None)
            df_combined["timestamp"] = df_combined["timestamp"].dt.floor("D")
        else:
            df_combined["timestamp"] = pd.to_datetime(df_combined["timestamp"]).dt.tz_convert("UTC").dt.tz_localize(None)
        df_combined.set_index("timestamp", inplace=True)
        df_combined = df_combined[["open", "high", "low", "close", "volume"]]
        df_combined.sort_index(inplace=True)
        return df_combined

    async def destroy(self):
        await self.client.aclose()
