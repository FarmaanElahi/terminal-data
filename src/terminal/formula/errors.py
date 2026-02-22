"""FormulaError — user-facing error with position, expected tokens, and hint."""


class FormulaError(Exception):
    """Raised when a formula string is invalid or cannot be evaluated.

    Attributes:
        message:  Plain-English description of what went wrong.
        formula:  The original formula string.
        position: 0-based character index where the problem was detected.
        expected: What the parser expected at that position (optional).
        hint:     Suggested fix (optional).
    """

    def __init__(
        self,
        message: str,
        *,
        formula: str = "",
        position: int | None = None,
        expected: str | None = None,
        hint: str | None = None,
    ):
        self.message = message
        self.formula = formula
        self.position = position
        self.expected = expected
        self.hint = hint
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"FormulaError: {self.message}"]
        if self.formula:
            parts.append(f"  Formula:  {self.formula}")
        if self.position is not None and self.formula:
            pointer = " " * self.position + "^"
            parts.append(f"  Position: {pointer}")
        if self.expected:
            parts.append(f"  Expected: {self.expected}")
        if self.hint:
            parts.append(f"  Hint:     {self.hint}")
        return "\n".join(parts)
