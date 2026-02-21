import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock
from terminal.scan.router import run_stateless
from terminal.scan.models import ScanStatelessRequest, ConditionParam, ColumnDef


def get_mock_ohlcv(symbol: str):
    df = pd.DataFrame(
        {
            "open": [100, 110],
            "high": [105, 115],
            "low": [95, 105],
            "close": [103, 112],
            "volume": [1000, 1200],
        },
        index=[1000, 2000],
    )
    df.index.name = "timestamp"
    for col in ["open", "high", "low", "close", "volume"]:
        df[col[0].upper()] = df[col]
    return df


@pytest.mark.asyncio
async def test_run_stateless_logic():
    # Setup mocks
    mock_user = MagicMock()
    mock_user.id = "test_user"

    mock_settings = MagicMock()
    mock_session = MagicMock()
    mock_fs = MagicMock()

    mock_market_manager = MagicMock()
    mock_market_manager.get_ohlcv.side_effect = lambda symbol, timeframe="D": (
        get_mock_ohlcv(symbol)
    )

    # Mock _resolve_symbols to return a list of symbols
    from terminal.scan import router

    router._resolve_symbols = AsyncMock(return_value=["AAPL"])

    # Run stateless scan
    scan_in = ScanStatelessRequest(
        source=None,
        conditions=[
            ConditionParam(
                formula="C > O",
                true_when="now",
                evaluation_type="boolean",
                type="computed",
            )
        ],
        conditional_logic="and",
        columns=[ColumnDef(id="Price", name="Price", type="value", expression="C")],
    )

    results = await run_stateless(
        scan_in=scan_in,
        user=mock_user,
        settings=mock_settings,
        session=mock_session,
        fs=mock_fs,
        market_manager=mock_market_manager,
    )

    # Verify results
    assert results["total"] == 1
    assert results["tickers"] == ["AAPL"]
    assert results["values"] == [[112.0]]
