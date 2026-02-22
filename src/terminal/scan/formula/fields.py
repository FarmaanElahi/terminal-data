"""Field registry for the formula engine.

Two kinds of fields:
  1. **Column fields** — map directly to a DataFrame column (e.g. C → "close")
  2. **Derived fields** — expand to an AST expression (e.g. HLC3 → (H+L+C)/3)

Adding a new field:
    register_column("VWAP", "vwap")                    # if DataFrame has a "vwap" column
    register_derived("HLC3", lambda: _hlc3_expr())      # computed from other fields

Both types support aliases:
    register_column("C", "close", aliases=["CLOSE"])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from terminal.scan.formula.ast_nodes import (
    BinOp,
    FieldRef,
    Node,
    NumberLiteral,
)


@dataclass(frozen=True, slots=True)
class ColumnField:
    """A field that maps directly to a DataFrame column."""

    name: str  # canonical short name (e.g. "C")
    column: str  # DataFrame column name (e.g. "close")


@dataclass(frozen=True, slots=True)
class DerivedField:
    """A field that expands to an AST expression at parse time."""

    name: str  # canonical name (e.g. "HLC3")
    builder: Callable[[], Node]  # returns a fresh AST subtree each call
    description: str = ""


# Global registries
_COLUMN_FIELDS: dict[str, ColumnField] = {}
_DERIVED_FIELDS: dict[str, DerivedField] = {}
_ALL_ALIASES: dict[str, str] = {}  # alias → canonical name (for both types)

# Single-char field shorthands valid in compact syntax (SMAC126)
_SHORTHANDS: set[str] = set()


def register_column(
    name: str,
    column: str,
    *,
    aliases: list[str] | None = None,
    shorthand: bool = False,
) -> None:
    """Register a column field that maps to a DataFrame column.

    Args:
        name: Canonical name (e.g. "C"). Will be uppercased.
        column: DataFrame column name (e.g. "close").
        aliases: Alternative names (e.g. ["CLOSE"]). Will be uppercased.
        shorthand: If True, this field's canonical name can be used in
                   compact function syntax (e.g. SMAC50).
    """
    key = name.upper()
    _COLUMN_FIELDS[key] = ColumnField(name=key, column=column)
    _ALL_ALIASES[key] = key

    if aliases:
        for alias in aliases:
            _ALL_ALIASES[alias.upper()] = key

    if shorthand:
        _SHORTHANDS.add(key)


def register_derived(
    name: str,
    builder: Callable[[], Node],
    *,
    description: str = "",
    aliases: list[str] | None = None,
) -> None:
    """Register a derived field that expands to an AST expression.

    Args:
        name: Canonical name (e.g. "HLC3"). Will be uppercased.
        builder: Callable returning a fresh AST Node each invocation.
        description: Human-readable description.
        aliases: Alternative names.
    """
    key = name.upper()
    _DERIVED_FIELDS[key] = DerivedField(
        name=key, builder=builder, description=description
    )
    _ALL_ALIASES[key] = key

    if aliases:
        for alias in aliases:
            _ALL_ALIASES[alias.upper()] = key


# --- Query API ---


def resolve(name: str) -> str | None:
    """Resolve *name* to its canonical field name, or None if unknown."""
    return _ALL_ALIASES.get(name.upper())


def get_column(canonical: str) -> str | None:
    """Return the DataFrame column name for a column field, or None."""
    cf = _COLUMN_FIELDS.get(canonical)
    return cf.column if cf else None


def get_derived_builder(canonical: str) -> Callable[[], Node] | None:
    """Return the AST builder for a derived field, or None."""
    df = _DERIVED_FIELDS.get(canonical)
    return df.builder if df else None


def is_column_field(canonical: str) -> bool:
    return canonical in _COLUMN_FIELDS


def is_derived_field(canonical: str) -> bool:
    return canonical in _DERIVED_FIELDS


def is_known(name: str) -> bool:
    """Check if *name* (or alias) is a registered field."""
    return name.upper() in _ALL_ALIASES


def shorthand_chars() -> set[str]:
    """Return the set of single-char field names valid in compact syntax."""
    return _SHORTHANDS.copy()


def all_field_names() -> list[str]:
    """Return sorted list of all canonical field names."""
    return sorted(set(list(_COLUMN_FIELDS.keys()) + list(_DERIVED_FIELDS.keys())))


def field_help() -> str:
    """Return a human-readable help string listing all fields."""
    parts = []
    for name in sorted(_COLUMN_FIELDS):
        cf = _COLUMN_FIELDS[name]
        parts.append(f"{name} ({cf.column.title()})")
    for name in sorted(_DERIVED_FIELDS):
        df = _DERIVED_FIELDS[name]
        desc = df.description or name
        parts.append(f"{name} ({desc})")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Built-in registrations
# ---------------------------------------------------------------------------

# Column fields — OHLCV
register_column("C", "close", aliases=["CLOSE"], shorthand=True)
register_column("O", "open", aliases=["OPEN"], shorthand=True)
register_column("H", "high", aliases=["HIGH"], shorthand=True)
register_column("L", "low", aliases=["LOW"], shorthand=True)
register_column("V", "volume", aliases=["VOLUME"], shorthand=True)


# Derived fields
def _hlc3() -> Node:
    """(H + L + C) / 3"""
    return BinOp(
        "/",
        BinOp("+", BinOp("+", FieldRef("H"), FieldRef("L")), FieldRef("C")),
        NumberLiteral(3.0),
    )


def _hl2() -> Node:
    """(H + L) / 2"""
    return BinOp("/", BinOp("+", FieldRef("H"), FieldRef("L")), NumberLiteral(2.0))


def _ohlc4() -> Node:
    """(O + H + L + C) / 4"""
    return BinOp(
        "/",
        BinOp(
            "+",
            BinOp("+", BinOp("+", FieldRef("O"), FieldRef("H")), FieldRef("L")),
            FieldRef("C"),
        ),
        NumberLiteral(4.0),
    )


register_derived("HLC3", _hlc3, description="Typical Price")
register_derived("HL2", _hl2, description="Median Price")
register_derived("OHLC4", _ohlc4, description="Average Price")
