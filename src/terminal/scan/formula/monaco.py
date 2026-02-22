"""Monaco Editor configuration generator for the formula language.

Produces a JSON-serialisable dict that contains everything a frontend
needs to register a custom Monaco language:
  - Monarch tokenizer rules (syntax highlighting)
  - Language configuration (brackets, autoClosingPairs, etc.)
  - Autocompletion items (fields, functions, keywords, derived fields)
"""

from __future__ import annotations

from terminal.scan.formula import fields
from terminal.scan.formula.functions import registered_names, get_func


def editor_config() -> dict:
    """Return the full Monaco editor configuration as a dict."""
    return {
        "languageId": "formula",
        "tokenizerRules": _tokenizer_rules(),
        "languageConfig": _language_config(),
        "completionItems": _completion_items(),
    }


def _tokenizer_rules() -> dict:
    """Monarch tokenizer rules for syntax highlighting."""
    func_names = registered_names()
    field_names = fields.all_field_names()

    # Collect all aliases for fields
    all_aliases = set()
    for name in field_names:
        all_aliases.add(name)
    for alias in ["CLOSE", "OPEN", "HIGH", "LOW", "VOLUME"]:
        all_aliases.add(alias)

    return {
        "defaultToken": "",
        "ignoreCase": True,
        "tokenizer": {
            "root": [
                # Whitespace
                ["\\s+", "white"],
                # Numbers (integer and decimal)
                ["\\d+\\.\\d+", "number.float"],
                ["\\d+", "number"],
                # Boolean operators (must come before identifier rule)
                ["\\b(AND|OR|NOT)\\b", "keyword"],
                # Functions — matched before generic identifiers
                [
                    "\\b(" + "|".join(func_names) + ")\\b",
                    "function",
                ],
                # Fields
                [
                    "\\b(" + "|".join(sorted(all_aliases | set(field_names))) + ")\\b",
                    "variable",
                ],
                # Identifiers (unknown — will be highlighted as error)
                ["[A-Za-z_][A-Za-z0-9_]*", "identifier"],
                # Comparison operators (two-char first)
                [">=|<=|==|!=", "operator.comparison"],
                [">|<", "operator.comparison"],
                # Arithmetic operators
                ["[+\\-*/]", "operator.arithmetic"],
                # Dot (shift operator)
                ["\\.", "delimiter"],
                # Parentheses
                ["[()]", "delimiter.parenthesis"],
                # Comma
                [",", "delimiter.comma"],
            ],
        },
    }


def _language_config() -> dict:
    """Monaco language configuration (brackets, etc.)."""
    return {
        "brackets": [["(", ")"]],
        "autoClosingPairs": [{"open": "(", "close": ")"}],
        "surroundingPairs": [{"open": "(", "close": ")"}],
    }


def _completion_items() -> list[dict]:
    """Autocompletion items for Monaco."""
    items = []

    # ── Keywords ──
    for kw in ["AND", "OR", "NOT"]:
        items.append(
            {
                "label": kw,
                "kind": "keyword",
                "detail": "Boolean operator",
                "insertText": kw,
            }
        )

    # ── Column fields ──
    for name in sorted(fields.all_field_names()):
        if fields.is_column_field(name):
            col = fields.get_column(name)
            items.append(
                {
                    "label": name,
                    "kind": "field",
                    "detail": f"Column: {col}",
                    "documentation": f"DataFrame column '{col}'. Shorthand for {col.title()} price.",
                    "insertText": name,
                }
            )

    # ── Derived fields ──
    for name in sorted(fields.all_field_names()):
        if fields.is_derived_field(name):
            builder = fields.get_derived_builder(name)
            desc = ""
            if builder and builder.__doc__:
                desc = builder.__doc__.strip()
            items.append(
                {
                    "label": name,
                    "kind": "field",
                    "detail": f"Derived: {desc}" if desc else "Derived field",
                    "documentation": f"Computed field that expands to: {desc}",
                    "insertText": name,
                }
            )

    # ── Functions (with snippet) ──
    for fn_name in registered_names():
        func_def = get_func(fn_name)
        # Build snippet: SMA(${1:source}, ${2:period})
        params = ["${1:source}"]
        for i in range(1, func_def.n_args):
            params.append(f"${{{i + 1}:param{i}}}")
        snippet = f"{fn_name}({', '.join(params)})"

        items.append(
            {
                "label": fn_name,
                "kind": "function",
                "detail": f"{fn_name}({', '.join(['source'] + [f'param{i}' for i in range(1, func_def.n_args)])})",
                "documentation": f"Built-in function: {fn_name}. Takes {func_def.n_args} arguments.",
                "insertText": snippet,
                "insertTextRules": "insertAsSnippet",
            }
        )

        # Also add shorthand variants for 2-arg functions
        if func_def.n_args == 2:
            for field_char in sorted(fields.shorthand_chars()):
                shorthand_label = f"{fn_name}{field_char}"
                col = fields.get_column(field_char) or field_char
                items.append(
                    {
                        "label": shorthand_label,
                        "kind": "function",
                        "detail": f"{fn_name}({field_char}, period) — shorthand",
                        "documentation": f"Compact syntax: {shorthand_label}N expands to {fn_name}({field_char}, N). Source is {col.title()}.",
                        "insertText": f"{shorthand_label}${{1:20}}",
                        "insertTextRules": "insertAsSnippet",
                    }
                )

    return items
