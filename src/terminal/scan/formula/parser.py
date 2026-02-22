"""Recursive-descent parser — formula string → AST.

Grammar (lowest → highest precedence):

    or_expr     = and_expr ( "OR"  and_expr )*
    and_expr    = not_expr ( "AND" not_expr )*
    not_expr    = "NOT" not_expr | comparison
    comparison  = add_expr ( ( ">" | "<" | ">=" | "<=" | "==" | "!=" ) add_expr )?
    add_expr    = mul_expr ( ( "+" | "-" ) mul_expr )*
    mul_expr    = unary    ( ( "*" | "/" ) unary )*
    unary       = "-" unary | atom
    atom        = NUMBER
               | IDENT "(" args ")"     — function call
               | IDENT ( "." NUMBER )?  — field (with optional shift)
               | FUNCFIELD_PERIOD       — shorthand e.g. SMAC126 → SMA(C,126)
               | "(" or_expr ")"
"""

from __future__ import annotations

from terminal.scan.formula.ast_nodes import (
    BinOp,
    FieldRef,
    FuncCall,
    Node,
    NumberLiteral,
    ShiftExpr,
    UnaryOp,
)
from terminal.scan.formula.errors import FormulaError
from terminal.scan.formula.functions import get_func, registered_names
from terminal.scan.formula.lexer import Token, TokenType, tokenize

# Single-char field shorthands valid in compact syntax (SMAC126)
_FIELD_SHORTHANDS = {"C", "O", "H", "L", "V"}

# Canonical field-name mapping (uppercase → short form).
_FIELD_ALIASES: dict[str, str] = {
    "C": "C",
    "CLOSE": "C",
    "O": "O",
    "OPEN": "O",
    "H": "H",
    "HIGH": "H",
    "L": "L",
    "LOW": "L",
    "V": "V",
    "VOLUME": "V",
}

# Reverse map for error messages
_FIELD_HELP = "C (Close), O (Open), H (High), L (Low), V (Volume)"


def parse(formula: str) -> Node:
    """Parse a formula string and return an AST ``Node``.

    The result is cacheable — it can be re-evaluated against different DataFrames
    without re-parsing.

    Raises ``FormulaError`` on any syntax or semantic error.
    """
    tokens = tokenize(formula)
    parser = _Parser(tokens, formula)
    node = parser.or_expr()
    parser.expect(TokenType.EOF)
    return node


class _Parser:
    """Stateful recursive-descent parser."""

    __slots__ = ("tokens", "pos", "formula")

    def __init__(self, tokens: list[Token], formula: str) -> None:
        self.tokens = tokens
        self.pos = 0
        self.formula = formula

    # --- helpers --------------------------------------------------------

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _match(self, *types: TokenType) -> Token | None:
        if self._peek().type in types:
            return self._advance()
        return None

    def expect(self, tt: TokenType) -> Token:
        tok = self._peek()
        if tok.type != tt:
            raise FormulaError(
                f"Expected {tt.name} but got {tok.value!r}",
                formula=self.formula,
                position=tok.pos,
                expected=tt.name,
            )
        return self._advance()

    # --- grammar rules --------------------------------------------------

    def or_expr(self) -> Node:
        left = self.and_expr()
        while self._match(TokenType.KW_OR):
            right = self.and_expr()
            left = BinOp("OR", left, right)
        return left

    def and_expr(self) -> Node:
        left = self.not_expr()
        while self._match(TokenType.KW_AND):
            right = self.not_expr()
            left = BinOp("AND", left, right)
        return left

    def not_expr(self) -> Node:
        if self._match(TokenType.KW_NOT):
            operand = self.not_expr()
            return UnaryOp("NOT", operand)
        return self.comparison()

    _CMP_OPS: dict[TokenType, str] = {
        TokenType.OP_GT: ">",
        TokenType.OP_LT: "<",
        TokenType.OP_GE: ">=",
        TokenType.OP_LE: "<=",
        TokenType.OP_EQ: "==",
        TokenType.OP_NE: "!=",
    }

    def comparison(self) -> Node:
        left = self.add_expr()
        tok = self._match(*self._CMP_OPS)
        if tok is not None:
            right = self.add_expr()
            return BinOp(self._CMP_OPS[tok.type], left, right)
        return left

    def add_expr(self) -> Node:
        left = self.mul_expr()
        while True:
            tok = self._match(TokenType.OP_ADD, TokenType.OP_SUB)
            if tok is None:
                break
            right = self.mul_expr()
            op = "+" if tok.type == TokenType.OP_ADD else "-"
            left = BinOp(op, left, right)
        return left

    def mul_expr(self) -> Node:
        left = self.unary()
        while True:
            tok = self._match(TokenType.OP_MUL, TokenType.OP_DIV)
            if tok is None:
                break
            right = self.unary()
            op = "*" if tok.type == TokenType.OP_MUL else "/"
            left = BinOp(op, left, right)
        return left

    def unary(self) -> Node:
        if self._match(TokenType.OP_SUB):
            operand = self.unary()
            return UnaryOp("-", operand)
        return self.atom()

    def atom(self) -> Node:
        tok = self._peek()

        # --- number literal ---
        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberLiteral(float(tok.value))

        # --- identifier: could be field, function call, or shorthand ---
        if tok.type == TokenType.IDENT:
            self._advance()
            name = tok.value  # already uppercased by lexer

            # Function call: IDENT "(" args ")"
            if self._peek().type == TokenType.LPAREN:
                node = self._parse_func_call(name, tok.pos)
                return self._try_shift(node)

            # Known field reference (possibly with shift)
            if name in _FIELD_ALIASES:
                return self._parse_field(name, tok.pos)

            # Try shorthand: SMAC126 → SMA(C, 126)
            shorthand = self._try_parse_shorthand(name, tok.pos)
            if shorthand is not None:
                return self._try_shift(shorthand)

            # Nothing matched — fall through to field error
            return self._parse_field(name, tok.pos)

        # --- parenthesised sub-expression ---
        if tok.type == TokenType.LPAREN:
            self._advance()
            node = self.or_expr()
            self.expect(TokenType.RPAREN)
            return self._try_shift(node)

        # --- nothing matched ---
        raise FormulaError(
            f"Unexpected token {tok.value!r}",
            formula=self.formula,
            position=tok.pos,
            expected="a number, field name, function call, or '('",
        )

    # --- sub-parsers -----------------------------------------------------

    def _try_shift(self, node: Node) -> Node:
        """If the next tokens are ``.N``, wrap *node* in a ``ShiftExpr``."""
        if self._peek().type != TokenType.DOT:
            return node
        self._advance()  # consume '.'
        num_tok = self._peek()
        if num_tok.type != TokenType.NUMBER:
            raise FormulaError(
                'Shift value must be a positive integer after "."',
                formula=self.formula,
                position=num_tok.pos,
            )
        self._advance()
        periods = int(float(num_tok.value))
        if periods == 0:
            raise FormulaError(
                "Shift of 0 means the current bar — remove the .0 suffix",
                formula=self.formula,
                position=num_tok.pos,
            )
        if periods < 0:
            raise FormulaError(
                "Shift value must be a positive integer.",
                formula=self.formula,
                position=num_tok.pos,
            )
        return ShiftExpr(node, periods)

    def _parse_field(self, name: str, pos: int) -> Node:
        canonical = _FIELD_ALIASES.get(name)
        if canonical is None:
            raise FormulaError(
                f'"{name}" is not a recognised field. Valid fields: {_FIELD_HELP}',
                formula=self.formula,
                position=pos,
            )
        node: Node = FieldRef(canonical)

        # shift: FIELD.N
        if self._peek().type == TokenType.DOT:
            self._advance()  # consume '.'
            num_tok = self._peek()
            if num_tok.type != TokenType.NUMBER:
                raise FormulaError(
                    f'Shift value must be a positive integer. "{name}.{num_tok.value}" is not valid '
                    "— try C.1, C.21, C.252, etc.",
                    formula=self.formula,
                    position=num_tok.pos,
                )
            self._advance()
            periods = int(float(num_tok.value))
            if periods == 0:
                raise FormulaError(
                    f"Shift of 0 means the current bar — just write {canonical} instead of {canonical}.0",
                    formula=self.formula,
                    position=num_tok.pos,
                )
            if periods < 0:
                raise FormulaError(
                    "Shift value must be a positive integer.",
                    formula=self.formula,
                    position=num_tok.pos,
                )
            node = ShiftExpr(node, periods)

        return node

    def _parse_func_call(self, name: str, pos: int) -> Node:
        # Validate function exists (will raise FormulaError if not)
        func_def = get_func(name, formula=self.formula, position=pos)

        self.expect(TokenType.LPAREN)
        args: list[Node] = []

        if self._peek().type != TokenType.RPAREN:
            args.append(self.or_expr())
            while self._match(TokenType.COMMA):
                args.append(self.or_expr())

        self.expect(TokenType.RPAREN)

        if len(args) != func_def.n_args:
            raise FormulaError(
                f"{name} requires {func_def.n_args} arguments: "
                f"{name}(source, period). Got {len(args)}.",
                formula=self.formula,
                position=pos,
            )

        return FuncCall(name, tuple(args))

    def _try_parse_shorthand(self, name: str, pos: int) -> Node | None:
        """Try to parse *name* as a shorthand function call.

        Pattern: ``FUNC_NAME`` + ``FIELD_SHORTHAND`` + ``PERIOD``
        e.g. ``SMAC126`` → ``SMA(C, 126)``, ``EMAV20`` → ``EMA(V, 20)``

        Returns the FuncCall node, or None if *name* doesn't match the pattern.
        Raises FormulaError if partial match (e.g. ``SMAC`` without a period).
        """
        func_names = registered_names()
        for fn in func_names:
            if not name.startswith(fn):
                continue
            rest = name[len(fn) :]  # e.g. "C126" from "SMAC126"
            if not rest:
                continue

            # First char of rest must be a field shorthand
            field_char = rest[0]
            if field_char not in _FIELD_SHORTHANDS:
                continue

            period_str = rest[1:]  # e.g. "126" from "C126"
            if not period_str:
                # Matched function + field but no period → error
                raise FormulaError(
                    f'"{name}" looks like shorthand for {fn}({field_char}, ??) '
                    f"but is missing the period number. "
                    f"Try {fn}{field_char}20 or {fn}({field_char}, 20).",
                    formula=self.formula,
                    position=pos,
                    hint=f"{fn}{field_char}20",
                )
            if not period_str.isdigit():
                continue

            period = int(period_str)
            if period == 0:
                raise FormulaError(
                    f'Period must be a positive integer. "{name}" has period 0.',
                    formula=self.formula,
                    position=pos,
                )

            # Validate arg count (source + period = 2)
            func_def = get_func(fn, formula=self.formula, position=pos)
            if func_def.n_args != 2:
                continue  # shorthand only works for 2-arg functions

            return FuncCall(
                fn,
                (FieldRef(field_char), NumberLiteral(float(period))),
            )

        return None
