"""ScreenerSession — per-screener state within a RealtimeSession."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import RealtimeSession

from .models import (
    CreateScreenerRequest,
    ModifyScreenerRequest,
    ScreenerParams,
    ScreenerRequest,
)

logger = logging.getLogger(__name__)


class ScreenerSession:
    """
    Holds state for a single screener subscription.

    Created via ``create_screener`` and stored inside the
    parent :class:`RealtimeSession`.  All screener-related messages
    (after creation) are forwarded here via :meth:`handle`.
    """

    def __init__(
        self,
        session_id: str,
        *,
        realtime: "RealtimeSession",
    ) -> None:
        self.session_id = session_id
        self.realtime = realtime
        self.params = ScreenerParams()

    async def handle(self, msg: ScreenerRequest) -> None:
        """Handle a screener request forwarded from the RealtimeSession."""
        match msg.m:
            case "create_screener":
                await self._handle_create_screener(msg)  # type: ignore[arg-type]
            case "modify_screener":
                await self._handle_modify_screener(msg)  # type: ignore[arg-type]
            case _:
                logger.warning("Unhandled screener message: %s", msg.m)

    async def _handle_create_screener(self, msg: CreateScreenerRequest) -> None:
        """Handle a create_screener request (initialization)."""
        # msg.p = (session_id,) OR (session_id, params)
        _, params = msg.p
        if params is not None:
            self.params = params

    async def _handle_modify_screener(self, msg: ModifyScreenerRequest) -> None:
        """Handle a modify_screener request."""
        # msg.p = (session_id, params)
        _, params = msg.p
        self.params = params

    def __repr__(self) -> str:
        return f"ScreenerSession(id={self.session_id!r})"
