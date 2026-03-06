import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_proxy_tv_library():
    from terminal.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        test_path = "charting_library/charting_library.standalone.js"
        proxy_url = f"/tv/{test_path}"

        with patch("terminal.proxy.client.send", new_callable=AsyncMock) as mock_send:
            mock_response = MagicMock()
            mock_response.status_code = 200
            content_text = b"console.log('TV library loaded');"
            mock_response.headers = {"content-type": "text/javascript"}

            async def mock_aiter_raw():
                yield content_text

            mock_response.aiter_raw = mock_aiter_raw
            mock_send.return_value = mock_response

            response = await client.get(proxy_url)

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/javascript"
            # Verify that we requested identity encoding from upstream
            args, _ = mock_send.call_args
            sent_request = args[0]
            assert sent_request.headers["accept-encoding"] == "identity"
            assert response.content == content_text
            assert response.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.asyncio
async def test_proxy_error_handling():
    from terminal.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("terminal.proxy.client.send", side_effect=Exception("Connection failed")):
            response = await client.get("/tv/charting_library/fail")
            assert response.status_code == 502
            assert "Connection failed" in response.text
