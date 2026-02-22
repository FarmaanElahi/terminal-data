"""AST node types produced by the formula parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Node:
    """Base class for all AST nodes."""


@dataclass(frozen=True, slots=True)
class NumberLiteral(Node):
    """A numeric constant (int or float)."""

    value: float


@dataclass(frozen=True, slots=True)
class FieldRef(Node):
    """Reference to a DataFrame column.

    ``name`` is the canonical short form: ``C``, ``O``, ``H``, ``L``, ``V``.
    """

    name: str


@dataclass(frozen=True, slots=True)
class ShiftExpr(Node):
    """A field shifted N bars into the past — e.g. ``C.21``."""

    expr: Node
    periods: int


@dataclass(frozen=True, slots=True)
class UnaryOp(Node):
    """Unary prefix operator (``-`` or ``NOT``)."""

    op: str  # "-" | "NOT"
    operand: Node


@dataclass(frozen=True, slots=True)
class BinOp(Node):
    """Binary operator — arithmetic, comparison, or boolean."""

    op: str  # "+", "-", "*", "/", ">", "<", ">=", "<=", "==", "!=", "AND", "OR"
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class FuncCall(Node):
    """Function invocation — e.g. ``SMA(C, 50)``."""

    name: str  # upper-cased canonical name
    args: tuple[Node, ...]
