"""Request logging and error handling middleware."""

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# Context variable for request ID propagation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Paths to skip in request logging to reduce noise
_SKIP_LOG_PATHS = {"/health", "/ready"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status, and duration for each HTTP request.

    Generates a UUID request_id per request, stores it in a ContextVar for
    downstream use, and adds it as an ``X-Request-ID`` response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = uuid.uuid4().hex[:12]
        request_id_var.set(rid)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "Unhandled error | %s %s | request_id=%s | %.1fms",
                request.method,
                request.url.path,
                rid,
                duration_ms,
            )
            return Response(
                content=f'{{"detail":"Internal server error","request_id":"{rid}"}}',
                status_code=500,
                media_type="application/json",
            )

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid

        if request.url.path not in _SKIP_LOG_PATHS:
            logger.info(
                "%s %s %d %.1fms request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                rid,
            )

        return response
