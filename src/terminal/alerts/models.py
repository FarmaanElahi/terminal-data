from __future__ import annotations

from terminal.models import TerminalBase


class AlertResponse(TerminalBase):
    """Unified alert response returned by all alert endpoints."""

    uuid: str
    name: str
    type: str  # "simple" | "ato"
    status: str  # "enabled" | "disabled" | "deleted"
    disabled_reason: str = ""
    lhs_exchange: str
    lhs_tradingsymbol: str
    lhs_attribute: str = "LastTradedPrice"
    operator: str  # "<=", ">=", "<", ">", "=="
    rhs_type: str  # "constant" | "instrument"
    rhs_constant: float | None = None
    rhs_attribute: str = ""
    rhs_exchange: str = ""
    rhs_tradingsymbol: str = ""
    alert_count: int = 0
    provider_id: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class AlertCreateRequest(TerminalBase):
    """Request body for creating an alert."""

    provider_id: str
    name: str
    type: str = "simple"  # "simple" | "ato"
    lhs_exchange: str
    lhs_tradingsymbol: str
    lhs_attribute: str = "LastTradedPrice"
    operator: str  # "<=", ">=", "<", ">", "=="
    rhs_type: str = "constant"
    rhs_constant: float | None = None
    rhs_attribute: str | None = None
    rhs_exchange: str | None = None
    rhs_tradingsymbol: str | None = None


class AlertModifyRequest(TerminalBase):
    """Request body for modifying an alert."""

    provider_id: str
    name: str | None = None
    type: str | None = None
    lhs_exchange: str | None = None
    lhs_tradingsymbol: str | None = None
    lhs_attribute: str | None = None
    operator: str | None = None
    rhs_type: str | None = None
    rhs_constant: float | None = None
    rhs_attribute: str | None = None
    rhs_exchange: str | None = None
    rhs_tradingsymbol: str | None = None


class AlertDeleteRequest(TerminalBase):
    """Request body for deleting alerts."""

    provider_id: str
    uuids: list[str]
