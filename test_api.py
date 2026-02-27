import asyncio
import os
import httpx
from dotenv import load_dotenv


async def main():
    load_dotenv()
    token = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
    key = "NSE_EQ|INE002A01018"
    import urllib.parse

    key = urllib.parse.quote(key)

    async with httpx.AsyncClient(
        base_url="https://api.upstox.com/v3",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    ) as client:
        path = f"/historical-candle/intraday/{key}/weeks/1"
        res = await client.get(path)
        print(
            "weeks",
            res.status_code,
            len(res.json().get("data", {}).get("candles", []))
            if res.status_code == 200
            else res.json(),
        )

        path = f"/historical-candle/intraday/{key}/months/1"
        res = await client.get(path)
        print(
            "months",
            res.status_code,
            len(res.json().get("data", {}).get("candles", []))
            if res.status_code == 200
            else res.json(),
        )


asyncio.run(main())
