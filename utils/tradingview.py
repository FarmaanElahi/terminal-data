import json
import requests
import pandas as pd
import numpy as np
from websockets.asyncio.client import connect
from typing import Any, Literal
from websockets import Origin, ClientConnection, ConnectionClosed
from string import ascii_letters, digits
from random import choices
from logging import Logger
from asyncio import create_task, gather

from utils.pandas_utils import to_datetime

_MESSAGE_PREFIX = "~m~"

log = Logger(__name__)


def _connect_to_server():
    url = "wss://data-wdc.tradingview.com/socket.io/websocket?type=chart"
    origin = "https://in.tradingview.com"
    return connect(url, origin=Origin(origin), max_size=None, ping_timeout=60)


def _encode(data: dict[str, Any] | list[dict[str, Any]] | str) -> str:
    encoded_message = ""
    if isinstance(data, str):
        encoded_message += f"{_MESSAGE_PREFIX}{len(data)}{_MESSAGE_PREFIX}{data}"
        return encoded_message

    if not isinstance(data, list):
        data = [data]

    for item in data:
        stringified = json.dumps(item) if item is not None else ""
        encoded_message += f"{_MESSAGE_PREFIX}{len(stringified)}{_MESSAGE_PREFIX}{stringified}"

    return encoded_message


async def _decode(socket: ClientConnection, msg: str) -> list[dict[str, Any]]:
    decoded_messages = []
    while msg.startswith(_MESSAGE_PREFIX):
        msg = msg[len(_MESSAGE_PREFIX):]
        separator_index = msg.find(_MESSAGE_PREFIX)
        length = int(msg[:separator_index])
        decoded_messages.append(
            msg[separator_index + len(_MESSAGE_PREFIX):separator_index + len(_MESSAGE_PREFIX) + length])
        msg = msg[separator_index + len(_MESSAGE_PREFIX) + length:]

    events = []
    for m in decoded_messages:
        if m.startswith("~h~"):
            await _send(socket, m)
        if m.startswith("{"):
            events.append(json.loads(m))
    return events


async def _init(socket: ClientConnection, tickers: list[str], data: dict[str, Any],
                mode: Literal["quote", "bar", "all"] = "all"):
    qs_session = _gen_session_id("qs")
    cs_session = _gen_session_id("cs")
    keys = {f"sds_sym_{i + 1}": {"t": tickers[i], "i": i + 1} for i in range(len(tickers))}

    # Store the key of the symbol that is completed
    data['quotes'] = {}
    data['bars'] = {}
    data['bar_completed'] = 0
    data['bar_started'] = []
    data['quote_completed'] = 0
    data['qs'] = qs_session
    data['cs'] = cs_session
    data['keys'] = keys

    await _send(socket, {"m": "set_auth_token", "p": ["unauthorized_user_token"]})
    await _send(socket, {"m": "set_locale", "p": ["en", "IN"]})

    if mode == "quote":
        data['bar_completed'] = len(tickers)

    if mode == "bar":
        data['quote_completed'] = len(tickers)

    if mode == "all" or mode == "quote":
        await _send(socket, {"m": "quote_create_session", "p": [qs_session]})
        await _send(socket, {"m": "quote_add_symbols", "p": [qs_session, *tickers]})
    if mode == "all" or mode == "bar":
        await _send(socket, {"m": "chart_create_session", "p": [cs_session, ""]})
        await _send(socket, {"m": "switch_timezone", "p": [cs_session, "Asia/Kolkata"]})
        resolve_request = []
        for symbol_key in keys:
            meta = keys[symbol_key]
            ticker = meta['t']
            p = json.dumps({"adjustment": "splits", "currency-id": "INR", "symbol": ticker})
            request = {"m": "resolve_symbol", "p": [cs_session, symbol_key, f'={p}']}
            resolve_request.append(request)
        await _send(socket, resolve_request)


async def _end(socket: ClientConnection):
    await socket.close()


def _gen_session_id(prefix: str):
    characters = ascii_letters + digits  # A-Z, a-z, 0-9
    random_string = ''.join(choices(characters, k=12))
    return f"{prefix}_{random_string}"


async def _send(socket: ClientConnection, data: str | dict[str, Any] | list[dict[str, Any]]):
    message = _encode(data)
    await socket.send(message)


async def _process_data(socket: ClientConnection, tickers: list[str], message: str | bytes, data: dict[str, Any]):
    events = await _decode(socket, message)

    for event in events:
        event_type = event.get("m")
        if event_type == "qsd":
            data['quotes'] = _on_qsd_event(event, data)
        if event_type == "quote_completed":
            completed_count = data['quote_completed']
            data["quote_completed"] = completed_count + 1
        if event_type == "symbol_resolved":
            await _on_symbol_resolved(socket, data)
        if event_type == "timescale_update":
            await _on_timescale_update(event, data)
        if event_type == "series_completed":
            await _on_series_completed(socket, tickers, data)

    return data.get("quote_completed", 0) == len(tickers) and data.get("bar_completed", 0) == len(tickers)


def _on_qsd_event(event: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    quotes = data.get("quotes", {})

    q: dict = event.get("p")[1]
    ticker = q.get("n")

    if q.get("v") is None:
        return quotes

    # Update Quote
    ticker_quote = quotes.get(ticker, {})
    q_data: dict = q.get("v")
    quotes[ticker] = ticker_quote | q_data

    return quotes


async def _on_symbol_resolved(socket: ClientConnection, data: dict[str, Any]):
    symbol_resolve_count = data.get("symbol_resolve_count", 0)
    symbol_resolve_count = symbol_resolve_count + 1
    data["symbol_resolve_count"] = symbol_resolve_count

    keys = data['keys']
    ticker_count = len(keys.keys())
    if symbol_resolve_count != ticker_count:
        # All symbol not yet resolved
        return

    bar_started = data['bar_started']
    to_start = list(set(keys.keys()) - set(bar_started))
    if len(to_start) == 0:
        return

    # Start with the first pending
    cs = data["cs"]
    symbol_key = to_start[0]
    series_id = f"s{keys[symbol_key]['i']}"

    # Request data
    await _send(socket, {"m": "create_series", "p": [cs, "sds_1", series_id, symbol_key, "1D", 5500]})
    bar_started.append(symbol_key)


async def _on_timescale_update(event: dict[str, Any], data: dict[str, Any]):
    p: dict[str, Any] = event.get("p")[1]
    series = p.get('sds_1')
    if series is None or series.get("s") is None:
        print("Series is missing", event)
        return

    # Day Data
    d = list(map(lambda s: s['v'], series.get("s")))

    keys = data['keys']
    bar_started = data['bar_started']
    bars = data['bars']

    # Mark the bars to loaded
    last_bar_key = bar_started[-1]
    ticker = keys[last_bar_key]['t']

    bar = bars.get(ticker, [])
    bars[ticker] = d + bar


async def _on_series_completed(socket: ClientConnection, ticker: list[str], data: dict[str, Any]):
    cs = data["cs"]
    keys = data['keys']
    bar_started = data['bar_started']
    bar_completed = data['bar_completed'] + 1
    data['bar_completed'] = bar_completed

    if bar_completed == len(ticker):
        return

    pending = list(set(keys.keys()) - set(bar_started))
    if len(pending) == 0:
        return

    symbol_key = pending[0]
    meta = keys[symbol_key]
    series_id = f"s{meta['i']}"

    await _send(socket, {"m": "modify_series", "p": [cs, "sds_1", series_id, symbol_key, "1D", ""]})
    bar_started.append(symbol_key)


async def download(tickers: list[str]):
    all_quotes = {}
    all_bars = {}
    async  for quotes, bars in fetch_bulk(tickers):
        all_quotes.update(quotes)
        all_bars.update(bars)

    return all_quotes, all_bars


def to_quote_df(quotes: dict[str, dict]):
    print("Generating Quote DataFrames...")
    quote_df = pd.DataFrame(quotes.values())
    quote_df['ticker'] = quote_df['pro_name']
    quote_df = quote_df.set_index(['ticker'])
    print("Generated Quote DataFrames...")
    return quote_df


def to_bars_df(bars: dict[str, list[list]]):
    required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

    def process_bar(bar):
        b_df = pd.DataFrame(bar)
        # Add column names dynamically (truncate to available data)
        b_df.columns = required_columns[:b_df.shape[1]]
        # Ensure all required columns are present
        for col in required_columns:
            if col not in b_df.columns:
                b_df[col] = np.nan  # Fill missing columns with NaN

        b_df['timestamp'] = pd.to_datetime(b_df['timestamp'], unit='s')
        b_df['timestamp'] = b_df['timestamp'].dt.floor('D')
        b_df.set_index(['timestamp'], inplace=True)
        return b_df

    print("Generating Bar DataFrames...")
    v = {k: process_bar(bar) for k, bar in bars.items()}
    print("Generated Bar DataFrames...")
    return v


async def fetch_bulk(tickers: list[str], mode: Literal["quote", "bar", "all"] = "all"):
    # Currently tradingview only allow 5 active websocket connections, so we spit the entire list into 500
    # Then to parallize the processing further, we split the request into 100 chunks of symbols again
    main_chunk = _chunk_list(tickers, 500)
    failed_chunks = []
    for idx, chunk in enumerate(main_chunk):
        print(f"Started: {idx + 1}/{len(main_chunk)}")
        sub_chunks = _chunk_list(chunk, 100)
        # Starts a new connection and fetches data fot this chunk only and closes the connection
        tasks = [create_task(_fetch_data(chunked_symbols, mode)) for chunked_symbols in sub_chunks]
        chunk_result = await gather(*tasks)
        for chunked_symbols, result in zip(sub_chunks, chunk_result):
            if result is None:
                print("Failed chunks: ", chunked_symbols)
                failed_chunks = failed_chunks + chunked_symbols
                continue

            # As soon as 100 symbol chunks are complete, it is yielded so that we can start processing it
            yield result

        print(f"Completed: {idx + 1}/{len(main_chunk)}")


async def _fetch_data(ticker: list[str], mode: Literal["quote", "bar", "all"] = "all"):
    if len(ticker) == 0:
        return {}, {}

    data = {}
    complete = False
    last_message = None
    async with (_connect_to_server() as socket):
        try:
            await _init(socket, ticker, data, mode)
            async  for message in socket:
                last_message = message
                complete = await _process_data(socket, ticker, message, data)
                if complete:
                    break
            await _end(socket)
        except ConnectionClosed as e:
            if not complete:
                print("Failed", last_message)
                log.error("Connection Closed", e)

    if complete:
        return data.get("quotes", {}), data.get("bars", {})

    return None


def _chunk_list(lst: list[str], chunk_size: int):
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


class TradingView:
    indexes = {
        "india": [
            "NSE:NIFTY", "NSE:NIFTYJR", "NSE:CNX500", "NSE:BANKNIFTY", "NSE:CNXFINANCE", "NSE:CNXIT",
            "NSE:CNXAUTO", "NSE:CNXPHARMA", "NSE:CNXPSUBANK", "NSE:CNXMETAL", "NSE:CNXFMCG", "NSE:CNXREALTY",
            "NSE:CNXMEDIA", "NSE:CNXINFRA", "NSE:NIFTYPVTBANK", "NSE:NIFTY_OIL_AND_GAS", "NSE:NIFTY_HEALTHCARE",
            "NSE:NIFTY_CONSR_DURBL", "NSE:CNX200", "NSE:NIFTY_MID_SELECT",
            "NSE:CNXSMALLCAP", "NSE:CNXMIDCAP", "NSE:CNXENERGY", "NSE:NIFTYMIDCAP50", "NSE:NIFTYSMLCAP250",
            "NSE:CNXPSE", "NSE:NIFTYMIDSML400", "NSE:NIFTYMIDCAP150", "NSE:CNXCONSUMPTION", "NSE:CNXCOMMODITIES",
            "NSE:NIFTY_MICROCAP250", "NSE:CPSE", "NSE:CNXSERVICE", "NSE:CNXMNC", "NSE:CNX100", "NSE:NIFTYALPHA50",
            "NSE:NIFTY_TOTAL_MKT", "NSE:NIFTY_INDIA_MFG",
            "NSE:NIFTY_IND_DIGITAL", "NSE:NIFTY_LARGEMID250", "BSE:SENSEX",
        ]
    }

    @staticmethod
    async def download(t: list[str]):
        all_quotes = {}
        all_bars = {}
        async  for quotes, bars in fetch_bulk(t):
            all_quotes.update(quotes)
            all_bars.update(bars)

        return all_quotes, all_bars

    @staticmethod
    async def download_quotes(t: list[str]):
        all_quotes = {}
        async  for quotes, bars in fetch_bulk(t):
            all_quotes.update(quotes)

        return all_quotes

    @staticmethod
    async def stream_quotes(t: list[str]):
        async  for quotes, bars in fetch_bulk(t, "quote"):
            for quote in quotes.values():
                df = pd.DataFrame([quote])
                df['ticker'] = df.pro_name
                df.set_index(["ticker"], inplace=True)
                yield df

    @staticmethod
    async def stream_candles(t: list[str]):
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        async  for quotes, bars in fetch_bulk(t, "bar"):
            for ticker, bar in bars.items():
                b_df = pd.DataFrame(bar)
                b_df.columns = required_columns[:b_df.shape[1]]
                # Ensure all required columns are present
                for col in required_columns:
                    if col not in b_df.columns:
                        b_df[col] = np.nan  # Fill missing columns with NaN
                b_df['timestamp'] = pd.to_datetime(b_df['timestamp'], unit='s')
                b_df['timestamp'] = b_df['timestamp'].dt.floor('D')
                b_df.set_index(['timestamp'], inplace=True)
                yield ticker, b_df

    @staticmethod
    def get_base_symbols(limit: int | None = None):
        market = "india"
        url = f"https://scanner.tradingview.com/{market}/scan"
        payload = {
            "columns": [
                "name",
                "type",
                "isin",
                "description",
                "logoid",
                "pricescale",
                "minmov",
                "currency",
                "fundamental_currency_code",
                "market",
                "sector",
                "industry.tr",
                "recommendation_mark",
                "exchange",
                "source-logoid",
                # Recent earning
                "earnings_release_trading_date_fq",
                # Upcoming earnings
                "earnings_release_next_trading_date_fq",
                "float_shares_outstanding_current",
                # Index part
                "indexes.tr",

                # Some fundamental
                "market_cap_basic",
                "price_earnings_ttm",
                "price_earnings_growth_ttm",
                "price_target_1y",
                "float_shares_percent_current",
                "High.All",
                "Low.All",
                "beta_1_year",
                "beta_3_year",
                "beta_5_year",
            ],
            "filter": [
                {
                    "left": "exchange",
                    "operation": "in_range",
                    "right": ["NSE"]
                }
            ],
            "sort": {
                "sortBy": "market_cap_basic",
                "sortOrder": "desc"
            },
        }
        headers = {'Content-Type': 'text/plain'}

        r = requests.request("POST", url, headers=headers, data=json.dumps(payload))
        r.raise_for_status()
        # [{'s': 'NYSE:HKD', 'd': []}, {'s': 'NASDAQ:ALTY', 'd': []}...]
        # Only 10 data in test mode
        data = r.json()['data'][:limit] if limit else r.json()['data']
        base = pd.DataFrame([[i['s'], *i['d']] for i in data], columns=["ticker", *payload["columns"]])
        base.rename(
            columns={
                "logoid": "logo",
                "source-logoid": "exchange_logo",
                "fundamental_currency_code": "fundamental_currency",
                "industry.tr": "industry",
                "indexes.tr": "indexes",
                "market_cap_basic": "mcap",
                "High.All": "all_time_high",
                "Low.All": "all_time_low",
                "float_shares_outstanding_current": "shares_float",
                "earnings_release_trading_date_fq":"earnings_release_date",
                "earnings_release_next_trading_date_fq":"earnings_release_next_date"
            },
            inplace=True
        )
        base.isin = base['isin'].astype(str)
        base.type = base['type'].astype('category')
        base.name = base['name'].astype(str)
        base.minmov = base['minmov'].astype('int16')
        base.pricescale = base['pricescale'].astype('int16')
        base.type = base['type'].astype('category')
        base.exchange = base['exchange'].astype('category')
        base.exchange_logo = base['exchange_logo'].astype('category')
        base.currency = base['currency'].astype('category')
        base.fundamental_currency = base['fundamental_currency'].astype('category')
        base.market = base['market'].astype('category')
        base.sector = base['sector'].astype('category')
        base.industry = base['industry'].astype('category')
        base.set_index(['ticker'], inplace=True)
        base.earnings_release_date = to_datetime(base.earnings_release_date)
        base.earnings_release_next_date = to_datetime(base.earnings_release_next_date)
        return base

    @staticmethod
    async def get_index(default_columns: list[str]):
        indexes = [
            "NSE:NIFTY", "NSE:NIFTYJR", "NSE:CNX500", "NSE:BANKNIFTY", "NSE:CNXFINANCE", "NSE:CNXIT",
            "NSE:CNXAUTO", "NSE:CNXPHARMA", "NSE:CNXPSUBANK", "NSE:CNXMETAL", "NSE:CNXFMCG", "NSE:CNXREALTY",
            "NSE:CNXMEDIA", "NSE:CNXINFRA", "NSE:NIFTYPVTBANK", "NSE:NIFTY_OIL_AND_GAS", "NSE:NIFTY_HEALTHCARE",
            "NSE:NIFTY_CONSR_DURBL", "NSE:CNX200", "NSE:NIFTY_MID_SELECT",
            "NSE:CNXSMALLCAP", "NSE:CNXMIDCAP", "NSE:CNXENERGY", "NSE:NIFTYMIDCAP50", "NSE:NIFTYSMLCAP250",
            "NSE:CNXPSE", "NSE:NIFTYMIDSML400", "NSE:NIFTYMIDCAP150", "NSE:CNXCONSUMPTION", "NSE:CNXCOMMODITIES",
            "NSE:NIFTY_MICROCAP250", "NSE:CPSE", "NSE:CNXSERVICE", "NSE:CNXMNC", "NSE:CNX100", "NSE:NIFTYALPHA50",
            "NSE:NIFTY_TOTAL_MKT", "NSE:NIFTY_INDIA_MFG",
            "NSE:NIFTY_IND_DIGITAL", "NSE:NIFTY_LARGEMID250", "BSE:SENSEX",
        ]
        index_data = await TradingView.download_quotes(indexes)

        q = pd.DataFrame(index_data.values())
        q['ticker'] = q['pro_name']
        q.set_index(["ticker"], inplace=True)

        i_df = pd.DataFrame([], columns=default_columns)
        i_df.name = q.short_name.astype(str)
        i_df.type = q.type.astype('category')
        i_df.description = q.description.astype(str)
        i_df.logo = q.logoid.astype(str)
        i_df.pricescale = q.pricescale
        i_df.minmov = q.minmov
        i_df.currency = q.currency_code.astype('category')
        i_df.fundamental_currency = i_df.currency
        i_df.market = 'india'
        i_df.exchange = q.exchange
        i_df.exchange = q.exchange
        i_df.exchange_logo = q['source-logoid'].astype('category')
        i_df.all_time_high = q.all_time_high
        i_df.all_time_low = q.all_time_low
        return i_df
