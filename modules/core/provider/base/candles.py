from abc import ABC, abstractmethod
from typing import Literal

import pandas as pd
import datetime
import asyncio


class CandleProvider(ABC):
    @abstractmethod
    async def prepare(self):
        pass

    async def stream(self,
                     ticker: list[str],
                     unit: Literal["minutes", "hours", "days", "weeks", "months"] = "days",
                     interval: int = 1,
                     to_date: datetime.date = datetime.date.today(),
                     duration: datetime.timedelta = datetime.timedelta(days=365),
                     concurrency: int = 20,
                     ) -> (str, pd.DataFrame, Exception | None):

        semaphore = asyncio.Semaphore(concurrency)  # Limit concurrency to 5

        async def fetch(symbol: str):
            async with semaphore:
                try:
                    df = await self.candles(
                        ticker=symbol,
                        unit=unit,
                        interval=interval,
                        to_date=to_date,
                        duration=duration,
                    )
                    return symbol, df, None
                except Exception as e:
                    return symbol, None, e

        tasks = [fetch(symbol) for symbol in ticker]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result

    @abstractmethod
    async def candles(self,
                      ticker: str,
                      unit: Literal["minutes", "hours", "days", "weeks", "months"] = "days",
                      interval: int = 1,
                      to_date: datetime.date = datetime.date.today(),
                      duration: datetime.timedelta = datetime.timedelta(days=365),
                      ) -> pd.DataFrame:
        pass

    @abstractmethod
    async def destroy(self):
        pass
