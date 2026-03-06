import logging
import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Proxy"])

TARGET_DOMAIN = "charting-library.tradingview-widget.com"
BASE_URL = f"https://{TARGET_DOMAIN}"

# Persistent async client
client = httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, follow_redirects=True)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_tv_library(path: str, request: Request):
    """
    Transparent streaming proxy to charting-library.tradingview-widget.com.
    Forces identity (uncompressed) encoding to avoid double-decoding issues
    when the response passes through multiple hops (e.g. Nginx → FastAPI).
    Mounted at /tv on the root app so /tv/<path> maps to /<path> upstream.
    """
    try:
        url_path = f"/{path}"
        params = dict(request.query_params)

        headers = dict(request.headers)
        headers["host"] = TARGET_DOMAIN

        # Force plaintext from upstream — prevents gibberish from double-proxying
        headers.pop("accept-encoding", None)
        headers["accept-encoding"] = "identity"

        body = await request.body()

        rp_resp = await client.send(
            client.build_request(
                method=request.method,
                url=url_path,
                params=params,
                headers=headers,
                content=body,
            ),
            stream=True,
        )

        res_headers = dict(rp_resp.headers)
        res_headers["Access-Control-Allow-Origin"] = "*"
        # Strip encoding/length headers — StreamingResponse manages these
        res_headers.pop("content-encoding", None)
        res_headers.pop("content-length", None)

        logger.info("Proxying %s → %d", path, rp_resp.status_code)

        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=res_headers,
        )

    except Exception as e:
        logger.exception("Proxy failed for %s", path)
        return Response(content=f"Proxy Error: {str(e)}", status_code=502)
