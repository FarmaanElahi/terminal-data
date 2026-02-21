import pytest
import json
from unittest.mock import patch, MagicMock
from terminal.tradingview.scanner import TradingViewScanner


@pytest.mark.asyncio
async def test_fetch_symbols_mock():
    scanner = TradingViewScanner()
    mock_resp = {
        "data": [
            {
                "s": "NSE:RELIANCE",
                "d": [
                    "Reliance Industries",
                    "logoid",
                    True,
                    "isin",
                    "NSE",
                    "IN",
                    "stock",
                    ["common"],
                    [],
                ],
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_resp

        results = await scanner.fetch_symbols(markets=["india"])
        assert len(results) == 1
        assert results[0]["ticker"] == "NSE:RELIANCE"
        assert results[0]["name"] == "Reliance Industries"
