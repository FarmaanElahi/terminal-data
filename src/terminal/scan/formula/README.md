# Formula Parser Engine

A custom TC2000-style formula language for evaluating analytical expressions against OHLCV DataFrames. Designed for real-time market scanning — parse once, evaluate across thousands of symbols with zero Python knowledge required.

---

## Quick Start

```python
from terminal.scan.formula import parse, evaluate, FormulaError

# Parse a formula string into a cacheable AST
ast = parse("C > SMA(C, 50) AND V > SMA(V, 20) * 1.5")

# Evaluate against any OHLCV DataFrame
result = evaluate(ast, df)  # → np.ndarray (bool or float64)

# Re-use the same AST across many symbols (no re-parsing cost)
for symbol_df in all_dataframes:
    result = evaluate(ast, symbol_df)
```

---

## Formula Language Reference

### Field Names

Both shorthand and full names are accepted. Case-insensitive.

| Shorthand | Full Name | DataFrame Column |
| --------- | --------- | ---------------- |
| `C`       | `CLOSE`   | `close`          |
| `O`       | `OPEN`    | `open`           |
| `H`       | `HIGH`    | `high`           |
| `L`       | `LOW`     | `low`            |
| `V`       | `VOLUME`  | `volume`         |

```
C > 100         ✓
close > 100     ✓
CLOSE > 100     ✓
```

### Shift (Lookback) — `.N`

Append `.N` to shift any value N bars into the past. Produces NaN for the first N rows.

**On fields:**

```
C.1       → Close from 1 bar ago
C.21      → Close from 21 bars ago
H.5       → High from 5 bars ago
```

**On function calls:**

```
SMA(C, 50).5      → 50-bar SMA shifted 5 bars back
EMA(V, 20).10     → 20-bar EMA of Volume from 10 bars ago
```

**On shorthand:**

```
SMAC126.1         → SMA(C, 126) shifted 1 bar
EMAC20.5          → EMA(C, 20) shifted 5 bars
```

**On parenthesised expressions:**

```
(H - L).3         → Bar range from 3 bars ago
```

Internally maps to `pd.Series.shift(N)` — a single vectorised operation.

### Arithmetic Operators

Standard math, element-wise across the full array. Standard precedence (`*` `/` before `+` `-`).

| Operator | Example    | Meaning                    |
| -------- | ---------- | -------------------------- |
| `+`      | `C + 1.5`  | Add 1.5 to every Close     |
| `-`      | `H - L`    | Bar range (High minus Low) |
| `*`      | `V * 0.5`  | Half the volume            |
| `/`      | `C / C.21` | Price ratio vs 21 bars ago |
| `-`      | `-C`       | Unary negation             |

### Comparison Operators

Produce a boolean array (`True`/`False` per bar).

| Operator | Example           |
| -------- | ----------------- |
| `>`      | `C > SMA(C, 50)`  |
| `<`      | `C < L.1`         |
| `>=`     | `C >= H.52`       |
| `<=`     | `V <= SMA(V, 20)` |
| `==`     | `C == O`          |
| `!=`     | `C != O`          |

### Boolean Operators

Combine boolean arrays. `NOT` binds tightest, then `AND`, then `OR`.

| Operator | Example                           |
| -------- | --------------------------------- |
| `AND`    | `C > SMA(C,50) AND V > SMA(V,20)` |
| `OR`     | `C < L.1 OR V > SMA(V,5) * 2`     |
| `NOT`    | `NOT C < SMA(C,200)`              |

### Operator Precedence (low → high)

| Level | Operators                 |
| ----- | ------------------------- |
| 1     | `OR`                      |
| 2     | `AND`                     |
| 3     | `NOT`                     |
| 4     | `> < >= <= == !=`         |
| 5     | `+ -`                     |
| 6     | `* /`                     |
| 7     | `-` (unary)               |
| 8     | `FIELD.N` `FUNC(…)` `(…)` |

Parentheses override precedence: `(H - L) / C * 100`

### User-Defined Parameters

Define named constants at the top of a formula with `param NAME = VALUE`. Parameters are resolved at parse time — zero runtime cost.

```
param period = 50
param threshold = 1.2

C / SMA(C, period) > threshold
```

Multiple parameters, used freely in any expression:

```
param fast = 12
param slow = 26

EMA(C, fast) > EMA(C, slow)
```

**Rules:**

- Case-insensitive: `param D = 10` and `param d = 10` both create param `D`
- Values must be numbers (integer or decimal)
- Cannot shadow reserved words (`AND`, `OR`, `NOT`), field names (`C`, `HLC3`), or function names (`SMA`)
- Each param name must be unique
- Param lines must come before the expression

### User-Defined Functions (UDFs)

Users can save parameterized formulas as reusable functions. Each UDF is referenced by its **ID** in formulas (so renaming the display name doesn't break anything).

Given a UDF with ID `ABC123`, body `C / SMA(C, d) > threshold`, and defaults `d=10, threshold=1.2`:

```
ABC123                                   → use with defaults
ABC123.1                                 → shifted 1 bar
ABC123#D#5                               → override d=5, threshold stays 1.2
ABC123#D#5#THRESHOLD#1.5                 → override both params
C > ABC123#THRESHOLD#2.0 AND V > SMAV20  → in compound formula
```

**Override syntax**: `ID#PARAM_NAME#VALUE` pairs, repeatable in any order.

**Rules:**

- Every param always has a default — only override what you need
- Unknown param names raise an error with available params listed
- UDFs can reference other UDFs (nested expansion)
- Supports `.N` shift after the ID (or after overrides)

### Built-in Functions

#### `SMA(source, period)` — Simple Moving Average

```
SMA(C, 20)           → 20-bar SMA of Close
SMA(V, 10)           → 10-bar SMA of Volume
SMA(H - L, 14)       → 14-bar SMA of bar range
```

- First `period - 1` rows are NaN
- Matches `pd.Series.rolling(period).mean()`

#### `EMA(source, period)` — Exponential Moving Average

```
EMA(C, 12)                   → 12-bar EMA of Close
EMA(C, 12) - EMA(C, 26)      → MACD line
EMA(C, 20) > EMA(C, 50)      → Trend filter
```

- Smoothing factor: `k = 2 / (period + 1)`
- Seeded with SMA of first N bars
- Matches `pd.Series.ewm(span=period, adjust=False).mean()`

### Shorthand Function Syntax

For 2-argument functions where the source is a single field (`C`, `O`, `H`, `L`, `V`), you can use a compact shorthand that **omits parentheses and commas**:

```
FUNC_NAME + FIELD + PERIOD
```

| Shorthand | Equivalent    | Meaning              |
| --------- | ------------- | -------------------- |
| `SMAC50`  | `SMA(C, 50)`  | 50-bar SMA of Close  |
| `EMAC20`  | `EMA(C, 20)`  | 20-bar EMA of Close  |
| `SMAV20`  | `SMA(V, 20)`  | 20-bar SMA of Volume |
| `EMAH126` | `EMA(H, 126)` | 126-bar EMA of High  |
| `SMAL10`  | `SMA(L, 10)`  | 10-bar SMA of Low    |

This works in any context — comparisons, compound conditions, arithmetic:

```
C > SMAC50                                    // Same as C > SMA(C, 50)
EMAC20 > EMAC50                               // Same as EMA(C, 20) > EMA(C, 50)
EMAC20 > EMAC50 AND V > SMAV20 * 1.5          // Fully compact compound
```

**Rules:**

- Case-insensitive: `smac50`, `SMAC50`, `Smac50` all work
- Period is required: `SMAC` alone is an error → _"missing the period number"_
- Period must be positive: `SMAC0` is an error
- Only works for 2-arg functions with a single field as source
- For complex sources like `SMA(H - L, 14)`, use the full syntax

### Derived Fields

Built-in computed fields that expand to their arithmetic equivalents at parse time.

| Field   | Expands To            | Meaning       |
| ------- | --------------------- | ------------- |
| `HLC3`  | `(H + L + C) / 3`     | Typical Price |
| `HL2`   | `(H + L) / 2`         | Median Price  |
| `OHLC4` | `(O + H + L + C) / 4` | Average Price |

They work everywhere — in comparisons, as function arguments, with shift:

```
HLC3 > 100                    // Typical price above 100
SMA(HLC3, 20)                 // 20-bar SMA of typical price
HLC3.5                        // Typical price from 5 bars ago
EMA(HL2, 12) > EMA(HL2, 26)   // EMA crossover on median price
OHLC4 > SMAC50                // Average price above 50-bar SMA of close
```

Case-insensitive: `hlc3`, `HLC3`, `Hlc3` all work. Adding new derived fields is one function + one dict entry in `parser.py`.

### Formula Examples

```
C / C.21 > 1.2                                    // 20% momentum
C > SMA(C, 50)                                    // Above 50-bar MA
C > SMAC50                                        // Same, shorthand
EMA(C, 20) > EMA(C, 50)                           // EMA crossover
EMAC20 > EMAC50                                   // Same, shorthand
V > SMA(V, 20) * 1.5                              // Volume surge
H < H.1 AND L > L.1                               // Inside bar
O > H.1                                           // Gap up
C > SMAC50 AND V > SMAV20 * 1.5                   // Compound, compact
SMA(C, 50).1                                      // Yesterday's SMA
SMAC50.1                                          // Same, shorthand
(H - L) / C * 100 > 3                             // Wide range bar
(H - L).3                                         // Range from 3 bars ago
NOT C < SMA(C, 200)                                // Not below 200 MA
SMA(HLC3, 20) > SMA(HLC3, 50)                     // Typical price trend
CLOSE / CLOSE.21 > 1.2 AND VOLUME > SMA(V, 20)    // Mixed names
```

---

## Architecture

```
                ┌──────────────────────────────────────────────┐
                │              Formula String                  │
                │  "C > SMA(C, 50) AND V > SMA(V, 20) * 1.5"  │
                └──────────────────┬───────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │     Lexer       │  lexer.py
                          │  (Tokenizer)    │
                          └────────┬────────┘
                                   │
                          list[Token]
                                   │
                          ┌────────▼────────┐
                          │     Parser      │  parser.py
                          │  (Recursive     │
                          │   Descent)      │
                          └────────┬────────┘
                                   │
                            AST (cacheable)
                                   │
                          ┌────────▼────────┐
                          │   Evaluator     │  evaluator.py
                          │  (Tree Walker)  │
                          │  + DataFrame    │
                          └────────┬────────┘
                                   │
                          np.ndarray (bool or float64)
```

### Module Files

| File           | Responsibility                                         |
| -------------- | ------------------------------------------------------ |
| `__init__.py`  | Public API: `parse()`, `evaluate()`, `FormulaError`    |
| `errors.py`    | `FormulaError` exception with position, expected, hint |
| `lexer.py`     | Tokenizer — formula string → `list[Token]`             |
| `ast_nodes.py` | Frozen dataclass AST nodes (immutable, cacheable)      |
| `parser.py`    | Recursive-descent parser — tokens → AST                |
| `evaluator.py` | Tree-walking evaluator — AST × DataFrame → NumPy array |
| `functions.py` | Function registry with SMA/EMA implementations         |

### Data Flow Detail

**Step 1 — Lexer** (`lexer.py`)

Converts the raw string into a flat list of typed `Token` objects. Each token carries its type, value, and source position (for error reporting).

```python
tokenize("C / C.21 > 1.2")
# → [IDENT("C"), OP_DIV("/"), IDENT("C"), DOT("."), NUMBER("21"),
#    OP_GT(">"), NUMBER("1.2"), EOF("")]
```

**Step 2 — Parser** (`parser.py`)

Consumes tokens using recursive descent, producing an AST that respects operator precedence:

```
BinOp(AND,
  BinOp(>, BinOp(/, FieldRef(C), ShiftExpr(FieldRef(C), 21)), NumberLiteral(1.2)),
  BinOp(>, FieldRef(V), BinOp(*, FuncCall(SMA, [FieldRef(V), NumberLiteral(20)]), NumberLiteral(1.5)))
)
```

The parser also handles:

- **Field resolution** — `CLOSE` → `C`, `volume` → `V` (case-insensitive)
- **Function validation** — checks the function exists in the registry and has the right arg count
- **Shift validation** — `C.0` is rejected, `C.x` is rejected

**Step 3 — Evaluator** (`evaluator.py`)

Recursively walks the AST, mapping each node to a NumPy operation:

| Node Type            | NumPy Operation                        |
| -------------------- | -------------------------------------- |
| `FieldRef("C")`      | `df["close"].to_numpy()`               |
| `ShiftExpr(C, 21)`   | `df["close"].shift(21).to_numpy()`     |
| `BinOp("/", …)`      | `np.divide(left, right)`               |
| `BinOp(">", …)`      | `np.greater(left, right)`              |
| `BinOp("AND", …)`    | `np.logical_and(left, right)`          |
| `FuncCall("SMA", …)` | `registry["SMA"].impl(source, period)` |
| `NumberLiteral(1.2)` | `np.float64(1.2)` — NumPy broadcasts   |

Every operation is vectorised. Zero Python-level row iteration.

### AST Nodes (`ast_nodes.py`)

All nodes are frozen dataclasses — immutable and safe to cache/reuse:

```python
@dataclass(frozen=True, slots=True)
class NumberLiteral(Node):
    value: float

@dataclass(frozen=True, slots=True)
class FieldRef(Node):
    name: str          # Canonical: "C", "O", "H", "L", "V"

@dataclass(frozen=True, slots=True)
class ShiftExpr(Node):
    expr: Node         # The expression to shift
    periods: int       # Bars to shift back

@dataclass(frozen=True, slots=True)
class UnaryOp(Node):
    op: str            # "-" or "NOT"
    operand: Node

@dataclass(frozen=True, slots=True)
class BinOp(Node):
    op: str            # "+", "-", "*", "/", ">", "<", "AND", "OR", etc.
    left: Node
    right: Node

@dataclass(frozen=True, slots=True)
class FuncCall(Node):
    name: str          # "SMA", "EMA", etc.
    args: tuple[Node, ...]
```

---

## Error Handling

All errors surface as `FormulaError` — never raw Python exceptions. Each error includes position info and a plain-English message suitable for end users.

```python
try:
    ast = parse("PRICE > 100")
except FormulaError as e:
    print(e)
```

Output:

```
FormulaError: "PRICE" is not a recognised field. Valid fields: C (Close), O (Open), H (High), L (Low), V (Volume)
  Formula:  PRICE > 100
  Position: ^^^^^
```

### Error Catalogue

| Trigger                | Error                                                            |
| ---------------------- | ---------------------------------------------------------------- |
| Unknown field `PRICE`  | `"PRICE" is not a recognised field. Valid fields: …`             |
| Unknown function `RSN` | `"RSN" is not a registered function. Did you mean SMA?`          |
| `SMA(C)`               | `SMA requires 2 arguments: SMA(source, period). Got 1.`          |
| `C.0`                  | `Shift of 0 means the current bar — just write C instead of C.0` |
| `C.x`                  | `Shift value must be a positive integer. "C.x" is not valid`     |
| Empty formula          | `Formula cannot be empty`                                        |
| `(C + H`               | `Expected RPAREN but got ''`                                     |
| `C @ 100`              | `Unexpected character "@"`                                       |

---

## Extensibility

Both functions and fields use a **registry pattern** — add new ones with a single call, zero parser changes.

### Adding a Function

```python
# In functions.py
from terminal.scan.formula.functions import register

def _rsi(source: np.ndarray, period: int) -> np.ndarray:
    delta = pd.Series(source).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return (100 - 100 / (1 + rs)).to_numpy()

register("RSI", 2, _rsi)
# Users can now write: RSI(C, 14) > 70, RSIC14 > 70
```

**Function contract**: accept `np.ndarray` source + numeric params, return `np.ndarray` of identical length, use `NaN` for insufficient history.

### Adding a Column Field

If your DataFrame has a new column (e.g. `vwap`):

```python
# In fields.py
from terminal.scan.formula.fields import register_column

register_column("VWAP", "vwap", aliases=["VP"], shorthand=True)
# Users can now write: VWAP > SMA(C, 20), or SMAVWAP50 if shorthand=True
```

### Adding a Derived Field

Computed from existing fields (no DataFrame column needed):

```python
# In fields.py
from terminal.scan.formula.fields import register_derived
from terminal.scan.formula.ast_nodes import BinOp, FieldRef, NumberLiteral

def _avghl3():
    """Custom: (H + L) / 2 + C / 3"""
    return BinOp("+",
        BinOp("/", BinOp("+", FieldRef("H"), FieldRef("L")), NumberLiteral(2.0)),
        BinOp("/", FieldRef("C"), NumberLiteral(3.0)),
    )

register_derived("AVGHL3", _avghl3, description="Custom Average")
# Users can now write: AVGHL3 > 100, SMA(AVGHL3, 20), AVGHL3.5
```

### Module Files (updated)

| File           | Responsibility                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------- |
| `__init__.py`  | Public API: `parse()`, `evaluate()`, `FormulaError`, `register_column()`, `register_derived()` |
| `fields.py`    | **Field registry** — column fields (OHLCV) + derived fields (HLC3, HL2, OHLC4)                 |
| `functions.py` | **Function registry** — SMA, EMA with extension pattern                                        |
| `errors.py`    | `FormulaError` exception with position, expected, hint                                         |
| `lexer.py`     | Tokenizer — formula string → `list[Token]`                                                     |
| `ast_nodes.py` | Frozen dataclass AST nodes (immutable, cacheable)                                              |
| `parser.py`    | Recursive-descent parser — tokens → AST                                                        |
| `evaluator.py` | Tree-walking evaluator — AST × DataFrame → NumPy array                                         |

---

## NaN Handling

| Situation                     | Behaviour                             |
| ----------------------------- | ------------------------------------- |
| Shift larger than history     | First N rows are NaN                  |
| SMA period > DataFrame length | Entire result is NaN                  |
| Division by zero              | `inf` or `NaN` per NumPy rules        |
| NaN in `AND`/`OR`             | NaN treated as `False`                |
| Last bar is NaN               | Scanner treats symbol as non-matching |

---

## Validate API Endpoint

```
POST /api/v1/scans/formula/validate
```

Test a formula against a real symbol's data without running a full scan.

**Request:**

```json
{
  "formula": "C > SMA(C, 50)",
  "symbol": "AAPL"
}
```

**Response (valid):**

```json
{
  "valid": true,
  "formula": "C > SMA(C, 50)",
  "symbol": "AAPL",
  "result_type": "bool",
  "last_value": true,
  "rows": 756
}
```

**Response (invalid formula):**

```json
{
  "valid": false,
  "formula": "PRICE > 100",
  "symbol": "AAPL",
  "error": "\"PRICE\" is not a recognised field. Valid fields: C (Close), O (Open), H (High), L (Low), V (Volume)"
}
```

---

## DataFrame Contract

The formula engine expects a pandas DataFrame with these **lowercase** columns:

| Column   | Type    |
| -------- | ------- |
| `open`   | float64 |
| `high`   | float64 |
| `low`    | float64 |
| `close`  | float64 |
| `volume` | float64 |

The index should be a timestamp (DatetimeIndex or numeric). The engine maps user-facing field names (`C`, `CLOSE`, etc.) to these column names internally.

---

## Performance

- **Parse time**: < 1ms for typical formulas (47 formulas parse in 0.03s total)
- **AST caching**: Parse once, evaluate across 10,000+ symbols without re-parsing
- **Vectorised evaluation**: Every operation maps to NumPy — no Python row loops
- **Zero overhead**: No `df.eval()`, no Python `engine="python"` interpreter

---

## Monaco Editor Integration

### Endpoint

```
GET /api/v1/scans/formula/editor-config
```

Returns a JSON object with everything needed to register the formula language in Monaco:

```json
{
  "languageId": "formula",
  "tokenizerRules": { ... },     // Monarch tokenizer (syntax highlighting)
  "languageConfig": { ... },     // Brackets, auto-closing pairs
  "completionItems": [ ... ]     // All fields, functions, keywords with snippets
}
```

The config is **dynamic** — it reflects the live registry. Any newly registered function or field appears automatically.

### Frontend Setup

```javascript
// 1. Fetch config from API
const res = await fetch("/api/v1/scans/formula/editor-config");
const config = await res.json();

// 2. Register the language
monaco.languages.register({ id: config.languageId });

// 3. Set language configuration (brackets, auto-closing)
monaco.languages.setLanguageConfiguration(
  config.languageId,
  config.languageConfig,
);

// 4. Set tokenizer for syntax highlighting
monaco.languages.setMonarchTokensProvider(
  config.languageId,
  config.tokenizerRules,
);

// 5. Register autocompletion provider
monaco.languages.registerCompletionItemProvider(config.languageId, {
  provideCompletionItems: (model, position) => {
    const word = model.getWordUntilPosition(position);
    const range = {
      startLineNumber: position.lineNumber,
      endLineNumber: position.lineNumber,
      startColumn: word.startColumn,
      endColumn: word.endColumn,
    };

    const kindMap = {
      keyword: monaco.languages.CompletionItemKind.Keyword,
      field: monaco.languages.CompletionItemKind.Variable,
      function: monaco.languages.CompletionItemKind.Function,
    };

    const suggestions = config.completionItems.map((item) => ({
      label: item.label,
      kind: kindMap[item.kind] || monaco.languages.CompletionItemKind.Text,
      detail: item.detail,
      documentation: item.documentation,
      insertText: item.insertText,
      insertTextRules:
        item.insertTextRules === "insertAsSnippet"
          ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet
          : undefined,
      range,
    }));

    return { suggestions };
  },
});

// 6. Define a theme with formula-specific token colors
monaco.editor.defineTheme("formulaTheme", {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "keyword", foreground: "C586C0" }, // AND, OR, NOT
    { token: "function", foreground: "DCDCAA" }, // SMA, EMA
    { token: "variable", foreground: "9CDCFE" }, // C, H, L, HLC3
    { token: "number", foreground: "B5CEA8" },
    { token: "number.float", foreground: "B5CEA8" },
    { token: "operator.comparison", foreground: "D4D4D4" },
    { token: "operator.arithmetic", foreground: "D4D4D4" },
    { token: "delimiter", foreground: "808080" },
    { token: "delimiter.parenthesis", foreground: "FFD700" },
    { token: "identifier", foreground: "FF6B6B" }, // Unknown → red
  ],
  colors: {},
});

// 7. Create the editor
const editor = monaco.editor.create(document.getElementById("formula-editor"), {
  value: "C > SMA(C, 50) AND V > SMAV20 * 1.5",
  language: config.languageId,
  theme: "formulaTheme",
  minimap: { enabled: false },
  lineNumbers: "off",
  glyphMargin: false,
  folding: false,
  wordWrap: "on",
  fontSize: 14,
  suggestOnTriggerCharacters: true,
  quickSuggestions: true,
});
```

### What Users Get

- **Syntax highlighting** — fields (blue), functions (yellow), keywords (purple), numbers (green), unknown identifiers (red)
- **Autocomplete** — type `SM` and get `SMA`, `SMAC`, `SMAH`, `SMAL`, `SMAO`, `SMAV` suggestions with snippet insertion
- **Snippets** — selecting `SMA` inserts `SMA(|source|, |period|)` with tab stops
- **Error highlighting** — unknown identifiers appear in red via the tokenizer
