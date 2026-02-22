"""Tokenizer for the formula language.

Produces a flat list of ``Token`` objects from a plain-text formula string.
All identifiers are normalised to uppercase.  Whitespace is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from terminal.scan.formula.errors import FormulaError


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()  # field name or function name — resolved later
    DOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()

    # Arithmetic
    OP_ADD = auto()
    OP_SUB = auto()
    OP_MUL = auto()
    OP_DIV = auto()

    # Comparison
    OP_GT = auto()
    OP_LT = auto()
    OP_GE = auto()
    OP_LE = auto()
    OP_EQ = auto()
    OP_NE = auto()

    # Boolean keywords
    KW_AND = auto()
    KW_OR = auto()
    KW_NOT = auto()

    HASH = auto()  # param override separator in UDFs

    EOF = auto()


# Keywords that map identifiers to boolean token types
_KEYWORDS: dict[str, TokenType] = {
    "AND": TokenType.KW_AND,
    "OR": TokenType.KW_OR,
    "NOT": TokenType.KW_NOT,
}


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: str
    pos: int  # 0-based character position in the source


def tokenize(formula: str) -> list[Token]:
    """Tokenize *formula* into a list of ``Token`` objects.

    Raises ``FormulaError`` on unrecognised characters.
    """
    if not formula or not formula.strip():
        raise FormulaError("Formula cannot be empty", formula=formula, position=0)

    tokens: list[Token] = []
    i = 0
    n = len(formula)

    while i < n:
        ch = formula[i]

        # --- skip whitespace ---
        if ch in " \t\r\n":
            i += 1
            continue

        # --- two-character operators ---
        two = formula[i : i + 2]
        if two == ">=":
            tokens.append(Token(TokenType.OP_GE, ">=", i))
            i += 2
            continue
        if two == "<=":
            tokens.append(Token(TokenType.OP_LE, "<=", i))
            i += 2
            continue
        if two == "==":
            tokens.append(Token(TokenType.OP_EQ, "==", i))
            i += 2
            continue
        if two == "!=":
            tokens.append(Token(TokenType.OP_NE, "!=", i))
            i += 2
            continue

        # --- single-character operators / punctuation ---
        if ch == "+":
            tokens.append(Token(TokenType.OP_ADD, "+", i))
            i += 1
            continue
        if ch == "-":
            tokens.append(Token(TokenType.OP_SUB, "-", i))
            i += 1
            continue
        if ch == "*":
            tokens.append(Token(TokenType.OP_MUL, "*", i))
            i += 1
            continue
        if ch == "/":
            tokens.append(Token(TokenType.OP_DIV, "/", i))
            i += 1
            continue
        if ch == ">":
            tokens.append(Token(TokenType.OP_GT, ">", i))
            i += 1
            continue
        if ch == "<":
            tokens.append(Token(TokenType.OP_LT, "<", i))
            i += 1
            continue
        if ch == "(":
            tokens.append(Token(TokenType.LPAREN, "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenType.RPAREN, ")", i))
            i += 1
            continue
        if ch == ",":
            tokens.append(Token(TokenType.COMMA, ",", i))
            i += 1
            continue
        if ch == ".":
            tokens.append(Token(TokenType.DOT, ".", i))
            i += 1
            continue
        if ch == "#":
            tokens.append(Token(TokenType.HASH, "#", i))
            i += 1
            continue

        # --- numbers: integer or decimal ---
        if ch.isdigit():
            start = i
            while i < n and formula[i].isdigit():
                i += 1
            if i < n and formula[i] == ".":
                i += 1
                while i < n and formula[i].isdigit():
                    i += 1
            tokens.append(Token(TokenType.NUMBER, formula[start:i], start))
            continue

        # --- identifiers (field names, function names, keywords) ---
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (formula[i].isalnum() or formula[i] == "_"):
                i += 1
            word = formula[start:i].upper()
            tt = _KEYWORDS.get(word, TokenType.IDENT)
            tokens.append(Token(tt, word, start))
            continue

        # --- unrecognised character ---
        raise FormulaError(
            f'Unexpected character "{ch}"',
            formula=formula,
            position=i,
            expected="a number, field name, operator, or parenthesis",
        )

    tokens.append(Token(TokenType.EOF, "", n))
    return tokens
