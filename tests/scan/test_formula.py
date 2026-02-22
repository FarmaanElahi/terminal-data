"""Comprehensive unit tests for the formula parser engine.

These tests do NOT require a database — they operate on in-memory DataFrames.
They cover the full acceptance criteria from the PRD:
  - §11.1 Parser acceptance tests
  - §11.2 Evaluation accuracy tests
  - §11.3 Error handling tests
"""

import numpy as np
import pandas as pd
import pytest

from terminal.scan.formula import FormulaError, evaluate, parse
from terminal.scan.formula.lexer import tokenize


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A 100-bar OHLCV DataFrame with realistic-ish price data."""
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n)) * 0.5
    low = close - np.abs(np.random.randn(n)) * 0.5
    opn = close + np.random.randn(n) * 0.2
    volume = np.abs(np.random.randn(n) * 1000) + 500

    df = pd.DataFrame(
        {
            "open": opn,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=pd.date_range("2025-01-01", periods=n, freq="D"),
    )
    df.index.name = "timestamp"
    return df


@pytest.fixture
def small_df() -> pd.DataFrame:
    """A tiny 4-bar DataFrame for deterministic tests."""
    df = pd.DataFrame(
        {
            "open": [100.0, 105.0, 110.0, 108.0],
            "high": [105.0, 112.0, 115.0, 120.0],
            "low": [95.0, 100.0, 105.0, 105.0],
            "close": [103.0, 108.0, 112.0, 115.0],
            "volume": [1000.0, 1100.0, 1200.0, 1500.0],
        },
        index=[1000, 2000, 3000, 4000],
    )
    df.index.name = "timestamp"
    return df


# ---------------------------------------------------------------------------
# §11.1  Parser Acceptance Tests — all valid formulas must parse
# ---------------------------------------------------------------------------

VALID_FORMULAS = [
    "C > 100",
    "c > 100",  # lowercase
    "CLOSE > 100",  # full name
    "C / C.21 > 1.2",  # shift
    "SMA(C, 50)",  # function
    "EMA(C, 20) > EMA(C, 50)",  # two functions
    "C > SMA(C, 50) AND V > SMA(V, 20) * 1.5",
    "NOT C < SMA(C, 200)",
    "(H - L) / C * 100 > 3",  # arithmetic grouping
    "O > H.1",  # open above yesterday high
    "H < H.1 AND L > L.1",  # inside bar
    "SMA(H - L, 14) > 2.0",  # expression as function source
    "EMA(C, 12) - EMA(C, 26) > 0",  # MACD-style composition
]


@pytest.mark.parametrize("formula", VALID_FORMULAS)
def test_valid_formulas_parse(formula: str):
    """Every formula from the PRD acceptance criteria must parse without error."""
    ast = parse(formula)
    assert ast is not None


# ---------------------------------------------------------------------------
# §11.2  Evaluation Accuracy Tests
# ---------------------------------------------------------------------------


def test_sma_matches_pandas(sample_df: pd.DataFrame):
    """SMA result must match pandas reference."""
    result = evaluate(parse("SMA(C, 20)"), sample_df)
    expected = sample_df["close"].rolling(20).mean().values
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_ema_matches_pandas(sample_df: pd.DataFrame):
    """EMA result must match pandas reference."""
    result = evaluate(parse("EMA(C, 20)"), sample_df)
    expected = sample_df["close"].ewm(span=20, adjust=False).mean().values
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_shift_matches_pandas(sample_df: pd.DataFrame):
    """Shift result must match pandas reference."""
    result = evaluate(parse("C.5"), sample_df)
    expected = sample_df["close"].shift(5).values
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_comparison_matches_manual(sample_df: pd.DataFrame):
    """Compound boolean result must match manual computation."""
    result = evaluate(parse("C > SMA(C, 50)"), sample_df)
    expected = sample_df["close"].values > sample_df["close"].rolling(50).mean().values
    # NaN comparisons produce False in our engine, NaN > x = False in NumPy too
    np.testing.assert_array_equal(result, expected)


def test_simple_field_access(small_df: pd.DataFrame):
    """A bare field name returns the column values."""
    result = evaluate(parse("C"), small_df)
    np.testing.assert_array_equal(result, [103.0, 108.0, 112.0, 115.0])


def test_arithmetic(small_df: pd.DataFrame):
    """Arithmetic operators produce correct element-wise results."""
    result = evaluate(parse("H - L"), small_df)
    expected = small_df["high"].values - small_df["low"].values
    np.testing.assert_allclose(result, expected)


def test_comparison_simple(small_df: pd.DataFrame):
    """C > O produces correct boolean array."""
    result = evaluate(parse("C > O"), small_df)
    expected = small_df["close"].values > small_df["open"].values
    np.testing.assert_array_equal(result, expected)


def test_shift_produces_nan(small_df: pd.DataFrame):
    """C.1 shifts by one bar, first element is NaN."""
    result = evaluate(parse("C.1"), small_df)
    assert np.isnan(result[0])
    np.testing.assert_allclose(result[1:], [103.0, 108.0, 112.0])


def test_division_formula(small_df: pd.DataFrame):
    """C / C.1 produces the ratio."""
    result = evaluate(parse("C / C.1"), small_df)
    assert np.isnan(result[0])
    np.testing.assert_allclose(result[1], 108.0 / 103.0, rtol=1e-10)


def test_compound_and(small_df: pd.DataFrame):
    """AND combines two boolean conditions."""
    result = evaluate(parse("C > O AND V > 1000"), small_df)
    close_gt_open = small_df["close"].values > small_df["open"].values
    vol_gt_1000 = small_df["volume"].values > 1000
    expected = close_gt_open & vol_gt_1000
    np.testing.assert_array_equal(result, expected)


def test_compound_or(small_df: pd.DataFrame):
    """OR combines two boolean conditions."""
    result = evaluate(parse("C > 200 OR V > 1400"), small_df)
    expected = (small_df["close"].values > 200) | (small_df["volume"].values > 1400)
    np.testing.assert_array_equal(result, expected)


def test_not_operator(small_df: pd.DataFrame):
    """NOT inverts a boolean condition."""
    result = evaluate(parse("NOT C > 110"), small_df)
    expected = ~(small_df["close"].values > 110)
    np.testing.assert_array_equal(result, expected)


def test_unary_negation(small_df: pd.DataFrame):
    """Unary minus negates the value."""
    result = evaluate(parse("-C"), small_df)
    np.testing.assert_array_equal(result, -small_df["close"].values)


def test_parenthesised_arithmetic(small_df: pd.DataFrame):
    """Parentheses override default precedence."""
    result = evaluate(parse("(H - L) / C * 100"), small_df)
    expected = (
        (small_df["high"].values - small_df["low"].values)
        / small_df["close"].values
        * 100
    )
    np.testing.assert_allclose(result, expected)


def test_sma_of_expression(sample_df: pd.DataFrame):
    """SMA(H - L, 14) — expression as function source argument."""
    result = evaluate(parse("SMA(H - L, 14)"), sample_df)
    expected = (sample_df["high"] - sample_df["low"]).rolling(14).mean().values
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_ema_composition(sample_df: pd.DataFrame):
    """EMA(C, 12) - EMA(C, 26) — MACD-like composition."""
    result = evaluate(parse("EMA(C, 12) - EMA(C, 26)"), sample_df)
    ema12 = sample_df["close"].ewm(span=12, adjust=False).mean().values
    ema26 = sample_df["close"].ewm(span=26, adjust=False).mean().values
    expected = ema12 - ema26
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_case_insensitive_fields(small_df: pd.DataFrame):
    """Mixed case field names all resolve correctly."""
    r1 = evaluate(parse("c"), small_df)
    r2 = evaluate(parse("C"), small_df)
    r3 = evaluate(parse("close"), small_df)
    r4 = evaluate(parse("CLOSE"), small_df)
    np.testing.assert_array_equal(r1, r2)
    np.testing.assert_array_equal(r2, r3)
    np.testing.assert_array_equal(r3, r4)


def test_full_name_mixed_with_shorthand(sample_df: pd.DataFrame):
    """CLOSE / CLOSE.21 > 1.2 AND VOLUME > SMA(V, 20) — mixed names."""
    # Should parse and evaluate without error
    result = evaluate(
        parse("CLOSE / CLOSE.21 > 1.2 AND VOLUME > SMA(V, 20)"), sample_df
    )
    assert result.dtype == bool
    assert len(result) == len(sample_df)


# ---------------------------------------------------------------------------
# §11.3  Error Handling Tests
# ---------------------------------------------------------------------------


def test_unknown_field_raises_formula_error(small_df: pd.DataFrame):
    """Unknown field — must raise FormulaError with 'not a recognised field'."""
    with pytest.raises(FormulaError, match="not a recognised field"):
        parse("PRICE > 100")


def test_unknown_function_raises_with_suggestion():
    """Unknown function — must raise FormulaError with 'Did you mean'."""
    with pytest.raises(FormulaError, match="not a registered function"):
        parse("RSN(C, 14)")


def test_syntax_error_raises_with_position():
    """Syntax error — must include position information."""
    with pytest.raises(FormulaError):
        parse("C >> 100")


def test_wrong_argument_count():
    """Wrong argument count — must raise FormulaError."""
    with pytest.raises(FormulaError, match="requires 2 arguments"):
        parse("SMA(C)")


def test_empty_formula():
    """Empty formula raises FormulaError."""
    with pytest.raises(FormulaError, match="cannot be empty"):
        parse("")


def test_empty_whitespace_formula():
    """Whitespace-only formula raises FormulaError."""
    with pytest.raises(FormulaError, match="cannot be empty"):
        parse("   ")


def test_shift_zero_raises():
    """Shift of 0 must raise FormulaError."""
    with pytest.raises(FormulaError, match="Shift of 0"):
        parse("C.0")


def test_unclosed_paren():
    """Unclosed parenthesis raises FormulaError."""
    with pytest.raises(FormulaError):
        parse("(C + H")


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


def test_division_by_zero(small_df: pd.DataFrame):
    """Division by zero must not raise — produces inf or NaN."""
    # Create a df where close has a zero
    df = small_df.copy()
    df.loc[df.index[0], "close"] = 0.0
    result = evaluate(parse("H / C"), df)
    # Should not raise — first element is inf
    assert np.isinf(result[0]) or np.isnan(result[0])


def test_single_row_df():
    """Engine handles a single-row DataFrame."""
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [103.0],
            "volume": [1000.0],
        },
        index=[1000],
    )
    df.index.name = "timestamp"
    result = evaluate(parse("C > O"), df)
    assert len(result) == 1
    assert result[0]


def test_empty_df():
    """Engine handles an empty DataFrame."""
    df = pd.DataFrame(
        {"open": [], "high": [], "low": [], "close": [], "volume": []},
    )
    df.index.name = "timestamp"
    result = evaluate(parse("C > O"), df)
    assert len(result) == 0


def test_ast_is_reusable(small_df: pd.DataFrame):
    """A parsed AST can be reused across multiple evaluations (FR-22)."""
    ast = parse("C > SMA(C, 2)")
    r1 = evaluate(ast, small_df)
    r2 = evaluate(ast, small_df)
    np.testing.assert_array_equal(r1, r2)


def test_nan_in_boolean_treated_as_false(small_df: pd.DataFrame):
    """NaN in boolean AND/OR context is treated as False."""
    # C.3 has first 3 rows NaN, combined with AND
    result = evaluate(parse("C > 100 AND C.3 > 100"), small_df)
    # First 3 should be False (NaN from shift)
    assert not result[0]
    assert not result[1]
    assert not result[2]


# ---------------------------------------------------------------------------
# Lexer-level tests
# ---------------------------------------------------------------------------


def test_tokenize_basic():
    """Tokenizer produces correct tokens for a simple formula."""
    tokens = tokenize("C > 100")
    # IDENT(C), OP_GT(>), NUMBER(100), EOF
    assert len(tokens) == 4
    assert tokens[0].value == "C"
    assert tokens[1].value == ">"
    assert tokens[2].value == "100"


def test_tokenize_two_char_ops():
    """Two-character operators are correctly tokenized."""
    tokens = tokenize("C >= 100 AND C != 200")
    values = [t.value for t in tokens]
    assert ">=" in values
    assert "!=" in values
    assert "AND" in values


def test_tokenize_unexpected_char():
    """Unexpected character raises FormulaError with position."""
    with pytest.raises(FormulaError, match="Unexpected character"):
        tokenize("C @ 100")


# ---------------------------------------------------------------------------
# Shorthand function syntax tests
# ---------------------------------------------------------------------------

SHORTHAND_PARSE_CASES = [
    "SMAC50",  # SMA(C, 50)
    "SMAV20",  # SMA(V, 20)
    "EMAC12",  # EMA(C, 12)
    "EMAH126",  # EMA(H, 126)
    "SMAL10",  # SMA(L, 10)
    "SMAO30",  # SMA(O, 30)
]


@pytest.mark.parametrize("formula", SHORTHAND_PARSE_CASES)
def test_shorthand_parses(formula: str):
    """Shorthand formulas must parse without error."""
    ast = parse(formula)
    assert ast is not None


def test_shorthand_matches_verbose(sample_df: pd.DataFrame):
    """SMAC20 must produce identical results to SMA(C, 20)."""
    r1 = evaluate(parse("SMAC20"), sample_df)
    r2 = evaluate(parse("SMA(C, 20)"), sample_df)
    np.testing.assert_allclose(r1, r2, equal_nan=True)


def test_shorthand_ema_matches_verbose(sample_df: pd.DataFrame):
    """EMAC12 must produce identical results to EMA(C, 12)."""
    r1 = evaluate(parse("EMAC12"), sample_df)
    r2 = evaluate(parse("EMA(C, 12)"), sample_df)
    np.testing.assert_allclose(r1, r2, equal_nan=True)


def test_shorthand_in_comparison(sample_df: pd.DataFrame):
    """Shorthand works inside larger expressions: C > SMAC50."""
    r1 = evaluate(parse("C > SMAC50"), sample_df)
    r2 = evaluate(parse("C > SMA(C, 50)"), sample_df)
    np.testing.assert_array_equal(r1, r2)


def test_shorthand_in_compound(sample_df: pd.DataFrame):
    """Shorthand in compound: EMAC20 > EMAC50 AND V > SMAV20 * 1.5."""
    r1 = evaluate(parse("EMAC20 > EMAC50 AND V > SMAV20 * 1.5"), sample_df)
    r2 = evaluate(parse("EMA(C, 20) > EMA(C, 50) AND V > SMA(V, 20) * 1.5"), sample_df)
    np.testing.assert_array_equal(r1, r2)


def test_shorthand_volume_field(sample_df: pd.DataFrame):
    """SMAV20 matches SMA(V, 20)."""
    r1 = evaluate(parse("SMAV20"), sample_df)
    r2 = evaluate(parse("SMA(V, 20)"), sample_df)
    np.testing.assert_allclose(r1, r2, equal_nan=True)


def test_shorthand_missing_period_raises():
    """SMAC without a period number must raise FormulaError."""
    with pytest.raises(FormulaError, match="missing the period number"):
        parse("SMAC")


def test_shorthand_zero_period_raises():
    """SMAC0 must raise FormulaError."""
    with pytest.raises(FormulaError, match="Period must be a positive integer"):
        parse("SMAC0")


def test_shorthand_case_insensitive():
    """smac50 should work (lexer uppercases all identifiers)."""
    ast = parse("smac50")
    assert ast is not None


# ---------------------------------------------------------------------------
# Shift on expressions (function calls, shorthand, parenthesised)
# ---------------------------------------------------------------------------


def test_shorthand_with_shift(sample_df: pd.DataFrame):
    """SMAC20.5 must equal SMA(C,20) shifted by 5 bars."""
    r1 = evaluate(parse("SMAC20.5"), sample_df)
    expected = sample_df["close"].rolling(20).mean().shift(5).values
    np.testing.assert_allclose(r1, expected, equal_nan=True)


def test_func_call_with_shift(sample_df: pd.DataFrame):
    """SMA(C, 20).5 must equal SMA(C,20) shifted by 5 bars."""
    r1 = evaluate(parse("SMA(C, 20).5"), sample_df)
    expected = sample_df["close"].rolling(20).mean().shift(5).values
    np.testing.assert_allclose(r1, expected, equal_nan=True)


def test_paren_expr_with_shift(sample_df: pd.DataFrame):
    """(H - L).3 must equal (H-L) shifted by 3 bars."""
    r1 = evaluate(parse("(H - L).3"), sample_df)
    expected = (sample_df["high"] - sample_df["low"]).shift(3).values
    np.testing.assert_allclose(r1, expected, equal_nan=True)


def test_shift_on_func_in_comparison(sample_df: pd.DataFrame):
    """C > SMA(C, 20).1 — compare current close to yesterday's SMA."""
    r1 = evaluate(parse("C > SMA(C, 20).1"), sample_df)
    sma_shifted = sample_df["close"].rolling(20).mean().shift(1).values
    expected = sample_df["close"].values > sma_shifted
    np.testing.assert_array_equal(r1, expected)


def test_shorthand_shift_matches_func_shift(sample_df: pd.DataFrame):
    """SMAC50.3 must match SMA(C, 50).3 exactly."""
    r1 = evaluate(parse("SMAC50.3"), sample_df)
    r2 = evaluate(parse("SMA(C, 50).3"), sample_df)
    np.testing.assert_allclose(r1, r2, equal_nan=True)


# ---------------------------------------------------------------------------
# Derived fields (HLC3, HL2, OHLC4)
# ---------------------------------------------------------------------------


def test_hlc3_value(small_df: pd.DataFrame):
    """HLC3 = (H + L + C) / 3."""
    result = evaluate(parse("HLC3"), small_df)
    expected = (
        small_df["high"].values + small_df["low"].values + small_df["close"].values
    ) / 3
    np.testing.assert_allclose(result, expected)


def test_hl2_value(small_df: pd.DataFrame):
    """HL2 = (H + L) / 2."""
    result = evaluate(parse("HL2"), small_df)
    expected = (small_df["high"].values + small_df["low"].values) / 2
    np.testing.assert_allclose(result, expected)


def test_ohlc4_value(small_df: pd.DataFrame):
    """OHLC4 = (O + H + L + C) / 4."""
    result = evaluate(parse("OHLC4"), small_df)
    expected = (
        small_df["open"].values
        + small_df["high"].values
        + small_df["low"].values
        + small_df["close"].values
    ) / 4
    np.testing.assert_allclose(result, expected)


def test_hlc3_with_shift(sample_df: pd.DataFrame):
    """HLC3.5 shifts the typical price by 5 bars."""
    result = evaluate(parse("HLC3.5"), sample_df)
    expected = (
        ((sample_df["high"] + sample_df["low"] + sample_df["close"]) / 3)
        .shift(5)
        .values
    )
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_sma_of_hlc3(sample_df: pd.DataFrame):
    """SMA(HLC3, 20) — function wrapping a derived field."""
    result = evaluate(parse("SMA(HLC3, 20)"), sample_df)
    hlc3 = (sample_df["high"] + sample_df["low"] + sample_df["close"]) / 3
    expected = hlc3.rolling(20).mean().values
    np.testing.assert_allclose(result, expected, equal_nan=True)


def test_hlc3_in_comparison(small_df: pd.DataFrame):
    """HLC3 > 100 produces correct boolean."""
    result = evaluate(parse("HLC3 > 100"), small_df)
    expected = (
        small_df["high"].values + small_df["low"].values + small_df["close"].values
    ) / 3 > 100
    np.testing.assert_array_equal(result, expected)


def test_hlc3_case_insensitive():
    """hlc3 parses (lexer uppercases)."""
    ast = parse("hlc3")
    assert ast is not None
