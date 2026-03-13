"""Data compression utilities for optimized API responses."""

from typing import Any, TypeVar

T = TypeVar("T", bound=dict)


def compress_objects(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compress array of objects to column-oriented format.

    Converts:
        [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]

    To:
        {
            "columns": ["a", "b"],
            "values": [[1, "x"], [2, "y"]]
        }

    This reduces payload size by eliminating repeated keys.

    Args:
        objects: List of dictionaries to compress

    Returns:
        Dictionary with "columns" and "values" keys
    """
    if not objects:
        return {"columns": [], "values": []}

    columns = list(objects[0].keys())
    values = [[obj.get(col) for col in columns] for obj in objects]

    return {"columns": columns, "values": values}


def decompress_objects(
    compressed: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Decompress column-oriented format back to array of objects.

    Converts:
        {
            "columns": ["a", "b"],
            "values": [[1, "x"], [2, "y"]]
        }

    To:
        [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]

    Args:
        compressed: Dictionary with "columns" and "values" keys

    Returns:
        List of dictionaries
    """
    columns = compressed.get("columns", [])
    values = compressed.get("values", [])

    return [dict(zip(columns, row)) for row in values]
