"""Manual test script for the screener flow.

Usage:
    python scripts/test_screener.py [--base-url http://localhost:8000]

Flow:
    1. Register & login
    2. Fetch all symbols from the symbols service
    3. Create a list with those symbols
    4. Create a condition set (C > SMA(C,20))
    5. Create a column set with filter
    6. Connect via WebSocket, create a screener, and print events
"""

import argparse
import asyncio
import json
import sys

import httpx
import websockets


async def main(base_url: str) -> None:
    api = f"{base_url}/api/v1"
    ws_url = base_url.replace("http", "ws") + "/ws"

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        # ── 1. Register & Login ──────────────────────────────────────
        print("▸ Registering user...")
        r = await client.post(
            f"{api}/auth/register",
            json={"username": "screener_test", "password": "screener_test"},
        )
        if r.status_code not in (200, 400):  # 400 = already exists
            print(f"  Register failed: {r.text}")
            sys.exit(1)

        print("▸ Logging in...")
        r = await client.post(
            f"{api}/auth/login",
            data={"username": "screener_test", "password": "screener_test"},
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  ✓ Token: {token[:20]}...")

        # ── 2. Fetch symbols ─────────────────────────────────────────
        print("▸ Fetching symbols...")
        r = await client.get(
            f"{api}/symbols/q",
            params={"market": "india", "limit": 20000},
            headers=headers,
        )
        assert r.status_code == 200, f"Symbols fetch failed: {r.text}"
        symbols_data = r.json()
        symbols = [item["ticker"] for item in symbols_data.get("items", [])]
        print(f"  ✓ Got {len(symbols)} symbols")

        if not symbols:
            print("  ⚠ No symbols found. Make sure symbols are synced.")
            symbols = ["NSE:RELIANCE", "NSE:TCS", "NSE:INFY"]
            print(f"  Using fallback symbols: {symbols}")

        # ── 3. Create a List ─────────────────────────────────────────
        print("▸ Creating list...")
        r = await client.post(
            f"{api}/lists/",
            headers=headers,
            json={"name": "Screener Test List", "type": "simple"},
        )
        assert r.status_code == 200, f"Create list failed: {r.text}"
        list_id = r.json()["id"]
        print(f"  ✓ List ID: {list_id}")

        print(f"▸ Adding {len(symbols)} symbols to list...")
        r = await client.post(
            f"{api}/lists/{list_id}/append_symbols",
            headers=headers,
            json={"symbols": symbols},
        )
        assert r.status_code == 200, f"Append symbols failed: {r.text}"
        print(f"  ✓ Added {len(symbols)} symbols")

        # ── 4. Create a Condition Set ────────────────────────────────
        print("▸ Creating condition set...")
        r = await client.post(
            f"{api}/conditions/",
            headers=headers,
            json={
                "name": "Price above SMA20",
                "conditions": [
                    {"formula": "C > SMA(C, 20)", "timeframe": "D"},
                ],
                "conditional_logic": "and",
                "timeframe": "fixed",
                "timeframe_value": "D",
            },
        )
        if r.status_code != 200:
            print(f"  ✗ Create condition set failed ({r.status_code}): {r.text}")
            sys.exit(1)
        condition_set_id = r.json()["id"]
        print(f"  ✓ Condition Set ID: {condition_set_id}")

        # ── 5. Create a Column Set ───────────────────────────────────
        print("▸ Creating column set...")
        r = await client.post(
            f"{api}/columns/",
            headers=headers,
            json={
                "name": "Test Screener Columns",
                "columns": [
                    {
                        "id": "col_close",
                        "name": "Close",
                        "type": "value",
                        "formula": "C",
                        "timeframe": "D",
                        "filter": "off",
                    },
                    {
                        "id": "col_sma20",
                        "name": "SMA 20",
                        "type": "value",
                        "formula": "SMA(C, 20)",
                        "timeframe": "D",
                        "filter": "off",
                    },
                    {
                        "id": "col_filtered",
                        "name": "Bullish Filter",
                        "type": "condition",
                        "formula": "C > SMA(C, 20)",
                        "timeframe": "D",
                        "condition_id": condition_set_id,
                        "condition_logic": "and",
                        "filter": "active",
                    },
                ],
            },
        )
        assert r.status_code == 200, f"Create column set failed: {r.text}"
        column_set_id = r.json()["id"]
        print(f"  ✓ Column Set ID: {column_set_id}")

        # ── 6. WebSocket Screener ────────────────────────────────────
        print(f"\n▸ Connecting to WebSocket at {ws_url}?token=...")
        async with websockets.connect(f"{ws_url}?token={token}") as ws:
            # Ping test
            await ws.send(json.dumps({"m": "ping"}))
            pong = json.loads(await ws.recv())
            assert pong["m"] == "pong", f"Expected pong, got {pong}"
            print("  ✓ Ping/pong OK")

            # Create screener
            create_msg = {
                "m": "create_screener",
                "p": [
                    "scr_test_1",
                    {
                        "source": list_id,
                        "column_set_id": column_set_id,
                        "filter_active": True,
                        "filter_interval": 10,
                    },
                ],
            }
            print(f"\n▸ Sending create_screener...")
            print(f"  → {json.dumps(create_msg, indent=2)}")
            await ws.send(json.dumps(create_msg))

            # Read responses
            print("\n▸ Waiting for responses (Ctrl+C to stop)...\n")
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg = json.loads(raw)
                    event = msg.get("m", "?")

                    if event == "screener_session_created":
                        print(f"  ✓ SESSION CREATED: {msg['p']}")
                    elif event == "screener_filter":
                        tickers = msg["p"][1]
                        print(f"  ✓ FILTER: {len(tickers)} tickers passed")
                        for t in tickers[:5]:
                            print(f"    - {t.get('ticker', t)}")
                        if len(tickers) > 5:
                            print(f"    ... and {len(tickers) - 5} more")
                    elif event == "screener_values":
                        cols = msg["p"][1]
                        print(f"  ✓ VALUES: {len(cols)} columns")
                        for col_id, vals in cols.items():
                            preview = vals[:3] if vals else []
                            print(
                                f"    {col_id}: {preview}{'...' if len(vals) > 3 else ''}"
                            )
                    elif event == "error":
                        print(f"  ✗ ERROR: {msg['p'][0]}")
                    else:
                        print(f"  ? {event}: {json.dumps(msg, indent=2)}")

            except asyncio.TimeoutError:
                print("  (no more messages after 30s)")
            except KeyboardInterrupt:
                print("\n  Stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the screener flow")
    parser.add_argument(
        "--base-url", default="http://localhost:8000", help="Base URL of the API"
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url))
