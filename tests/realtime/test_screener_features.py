import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pandas as pd
from terminal.realtime.screener import ScreenerSession
from terminal.realtime.models import CreateScreenerRequest, ScreenerParams
from terminal.column.models import ColumnDef


@pytest.fixture
def realtime_mock():
    mock = MagicMock()
    mock.user_id = "test_user"
    mock.send = AsyncMock()
    mock.manager = MagicMock()
    mock.manager.provider.fs = MagicMock()
    return mock


@pytest.fixture
def screener_session(realtime_mock):
    return ScreenerSession("test_sid", realtime=realtime_mock)


@pytest.mark.asyncio
async def test_screener_metadata_and_full_dataframe(realtime_mock, screener_session):
    # Mock data
    symbols = ["AAPL", "MSFT"]
    metadata = {
        "AAPL": {"name": "Apple Inc.", "logo": "apple-logo"},
        "MSFT": {"name": "Microsoft Corp.", "logo": "msft-logo"},
    }
    columns = [
        ColumnDef(
            id="price",
            name="Price",
            type="value",
            value_type="formula",
            value_formula="close",
        )
    ]

    screener_session.params = ScreenerParams(source="list1", columns=columns)
    screener_session._symbols = symbols
    screener_session._columns = columns
    screener_session._metadata = metadata

    # Mock OHLCV data for evaluation
    df_aapl = pd.DataFrame({"close": [150.0]}, index=[1000])
    df_msft = pd.DataFrame({"close": [300.0]}, index=[1000])

    realtime_mock.manager.get_ohlcv.side_effect = lambda s, **kwargs: (
        df_aapl if s == "AAPL" else df_msft
    )

    # Mock parse to return anything for the formula
    with patch("terminal.realtime.screener.parse", return_value=MagicMock()):
        with patch("terminal.realtime.screener.evaluate") as mock_eval:
            mock_eval.side_effect = lambda ast, df: df["close"].values

            # Initial evaluation
            screener_session._cache_formulas()
            await screener_session._run_filter(force=True)

            # Verify send was called with ScreenerFilterResponse
            assert realtime_mock.send.called
            response = realtime_mock.send.call_args[0][0]
            assert response.m == "screener_filter"

            session_id, rows, total = response.p
            assert session_id == "test_sid"
            assert total == 2
            assert len(rows) == 2

            # Check first row
            row0 = rows[0]
            assert row0.ticker == "AAPL"
            assert row0.name == "Apple Inc."
            assert row0.logo == "apple-logo"
            assert row0.v == {"price": 150.0}


@pytest.mark.asyncio
async def test_screener_field_type_column(realtime_mock, screener_session):
    # Mock data
    symbols = ["AAPL"]
    metadata = {
        "AAPL": {
            "name": "Apple Inc.",
            "logo": "apple-logo",
            "exchange": "NASDAQ",
            "sector": "Technology",
        }
    }
    columns = [
        ColumnDef(id="exchange", name="Exchange", type="value", value_type="field"),
        ColumnDef(id="sector", name="Sector", type="value", value_type="field"),
    ]

    screener_session.params = ScreenerParams(source="list1", columns=columns)
    screener_session._symbols = symbols
    screener_session._columns = columns
    screener_session._metadata = metadata
    screener_session._visible_tickers = symbols

    # Run column evaluation
    screener_session._cache_formulas()
    values = screener_session._evaluate_columns()

    assert "exchange" in values
    assert values["exchange"] == ["NASDAQ"]
    assert "sector" in values
    assert values["sector"] == ["Technology"]
