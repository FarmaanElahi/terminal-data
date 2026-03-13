"""Router for user-defined formula functions and editor tooling."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.auth.router import get_current_user
from terminal.dependencies import get_market_manager, get_session
from terminal.market_feed.manager import MarketDataManager
from terminal.formula import service
from terminal.formula.models import (
    FormulaCreate,
    FormulaPublic,
    FormulaValidateRequest,
    FormulaValidateResponse,
)

formulas = APIRouter(prefix="/formula", tags=["formulas"])


# ---------------------------------------------------------------------------
# UDF CRUD
# ---------------------------------------------------------------------------


@formulas.post("/functions", response_model=FormulaPublic)
async def create_formula(
    req: FormulaCreate,
    user: "User" = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a user-defined formula function."""
    try:
        return await service.create(session, user.id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@formulas.get("/functions", response_model=list[FormulaPublic])
async def list_formulas(
    user: "User" = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all user-defined formula functions."""
    return await service.all(session, user.id)


@formulas.delete("/functions/{formula_id}")
async def delete_formula(
    formula_id: str,
    user: "User" = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a user-defined formula function."""
    if not await service.delete(session, user.id, formula_id):
        raise HTTPException(status_code=404, detail="Formula not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Editor tooling
# ---------------------------------------------------------------------------


@formulas.get("/editor-config")
async def formula_editor_config():
    """Return Monaco editor configuration for the formula language."""
    from terminal.formula.monaco import editor_config

    return editor_config()


@formulas.post("/validate", response_model=FormulaValidateResponse)
async def validate_formula(
    req: FormulaValidateRequest,
    user: "User" = Depends(get_current_user),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
):
    """Validate a formula by parsing and evaluating it against a symbol's data."""
    import numpy as np

    from terminal.formula import FormulaError, evaluate, parse, preprocess

    # Fetch OHLCV data for the symbol
    df = market_manager.get_ohlcv(req.symbol, timeframe="D")
    if df is None or len(df) == 0:
        return FormulaValidateResponse(
            valid=False,
            formula=req.formula,
            symbol=req.symbol,
            error=f"No data available for symbol '{req.symbol}'",
        )

    # Preprocess (extract params) and parse
    try:
        body, params = preprocess(req.formula)
        ast = parse(body, params=params)
    except FormulaError as e:
        return FormulaValidateResponse(
            valid=False,
            formula=req.formula,
            symbol=req.symbol,
            error=e.message,
        )

    # Evaluate
    try:
        result = evaluate(ast, df)
        result = np.asarray(result)

        result_type = "bool" if result.dtype == bool else "float"
        last = result[-1] if len(result) > 0 else None

        # Convert numpy types to native Python
        if last is not None:
            if isinstance(last, (np.integer, np.floating)):
                last = last.item()
            elif isinstance(last, np.bool_):
                last = bool(last)

        return FormulaValidateResponse(
            valid=True,
            formula=req.formula,
            symbol=req.symbol,
            result_type=result_type,
            last_value=last,
            rows=len(result),
        )
    except FormulaError as e:
        return FormulaValidateResponse(
            valid=False,
            formula=req.formula,
            symbol=req.symbol,
            error=e.message,
        )
    except Exception as e:
        return FormulaValidateResponse(
            valid=False,
            formula=req.formula,
            symbol=req.symbol,
            error=str(e),
        )
