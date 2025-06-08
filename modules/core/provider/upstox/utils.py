from typing import Any
import json

INDEX_MAPPINGS: dict[str, str] = {
    "BSE:SENSEX": "BSE_INDEX|SENSEX",
    "NSE:CNXENERGY": "NSE_INDEX|Nifty Energy",
    "NSE:NIFTY_INDIA_MFG": "NSE_INDEX|Nifty India Mfg",
    "NSE:CNXINFRA": "NSE_INDEX|Nifty Infra",
    "NSE:CNXFMCG": "NSE_INDEX|Nifty FMCG",
    "NSE:CNXAUTO": "NSE_INDEX|Nifty Auto",
    "NSE:CNXIT": "NSE_INDEX|Nifty IT",
    "NSE:CNXFINANCE": "NSE_INDEX|Nifty Fin Service",
    "NSE:BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "NSE:CNX500": "NSE_INDEX|Nifty 500",
    "NSE:NIFTY": "NSE_INDEX|Nifty 50",
    "NSE:NIFTY_LARGEMID250": "NSE_INDEX|NIFTY LARGEMID250",
    # "NSE:NIFTY_IND_DIGITAL": "NSE_INDEX|",
    "NSE:CNXMNC": "NSE_INDEX|Nifty MNC",
    # "NSE:CNXSERVICE": "NSE_INDEX|",
    "NSE:NIFTY_TOTAL_MKT": "NSE_INDEX|NIFTY TOTAL MKT",
    "NSE:CPSE": "NSE_INDEX|Nifty CPSE",
    "NSE:NIFTY_MICROCAP250": "NSE_INDEX|NIFTY MICROCAP250",
    "NSE:CNXCOMMODITIES": "NSE_INDEX|Nifty Commodities",
    "NSE:NIFTYALPHA50": "NSE_INDEX|NIFTY Alpha 50",
    "NSE:CNXCONSUMPTION": "NSE_INDEX|Nifty Consumption",
    "NSE:NIFTYMIDCAP150": "NSE_INDEX|NIFTY MIDCAP 150",
    "NSE:CNX100": "NSE_INDEX|Nifty 100",
    # "NSE:NIFTYMIDSMAL400": "NSE_INDEX|",
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
}

# Caches
_forward_cache: dict[str, str] = {}  # symbol_json -> instrument_key
_reverse_cache: dict[str, str] = {}  # instrument_key -> symbol_dict


def to_upstox_instrument_key(symbol: dict[str, Any]) -> str | None:
    """
    Converts a symbol dict to an Upstox instrument key and caches it.
    """
    ticker = symbol.get("ticker")

    # Check forward cache
    if ticker in _forward_cache:
        return _forward_cache[ticker]

    type_ = symbol.get("type")
    exchange = symbol.get("exchange")
    isin = symbol.get("isin")

    if type_ == "index":
        instrument_key = INDEX_MAPPINGS.get(ticker)
        if not instrument_key:
            return None
    elif type_ in ("stock", "fund"):
        if not isin:
            return None
        instrument_key = f"{exchange}_EQ|{isin}"
    else:
        raise ValueError("Not supported symbol type")

    # Cache result in both directions
    _forward_cache[ticker] = instrument_key
    _reverse_cache[instrument_key] = ticker

    return instrument_key


def from_upstox_instrument_key(instrument_key: str) -> str:
    """
    Gets the original symbol dict from a cached instrument key.
    """
    symbol = _reverse_cache.get(instrument_key)
    if symbol is None:
        raise ValueError("Instrument key not found in reverse cache")
    return symbol
