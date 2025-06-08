from typing import Any, Literal

import duckdb
import pandas as pd
from duckdb import DuckDBPyConnection

from utils.bucket import storage_options, data_bucket

_con: DuckDBPyConnection | None = None


def refresh_data():
    print("Refreshing symbol data")
    data_df = pd.read_parquet(f'oci://{data_bucket}/symbols-full-v2.parquet', storage_options=storage_options)
    data_df.reset_index(inplace=True)

    global _con
    if _con is not None:
        _con.close()
    _con = duckdb.connect()
    _con.query("SET default_null_order = 'nulls_last';")
    _con.register("symbols", data_df)  # Expose as a table named 'data'
    print("Symbol refreshed")
    return _con


def get_con():
    global _con
    if _con is None:
        return refresh_data()
    return _con


def query_symbols(
        columns: list[str] = None,
        filters: list[dict[str, Any]] = None,
        filter_merge: Literal["OR", "AND"] = "AND",
        sort_fields: list[dict[str, str]] = None,
        limit: int | None = None,
        offset: int | None = None,
        universe: list[str] | None = None
):
    con = get_con()
    query = build_sql(
        columns=columns,
        filters=filters,
        filter_merge=filter_merge,
        sort_fields=sort_fields,
        limit=limit,
        offset=offset,
        table_name="symbols",
        universe=universe
    )
    return con.execute(query).fetchdf()


def close_con():
    if _con is not None:
        _con.close()


def build_sql(
        table_name: str,
        columns: list[str] = None,
        filters: list[dict[str, Any]] = None,
        filter_merge: Literal["OR", "AND"] = "AND",
        sort_fields: list[dict[str, str]] = None,
        limit: int | None = None,
        offset: int | None = None,
        universe: list[str] | None = None
) -> str:
    """
    Build complete SQL query

    Args:
        table_name: Name of the table to query
        columns: List of column names to select (defaults to *)
        filters: List of filter dictionaries
        filter_merge: How to combine multiple filters - "OR" or "AND"
        sort_fields: List of sort dictionaries with 'field' and 'direction' keys
        limit: Maximum number of rows to return
        offset: Number of rows to skip
        universe: Universe of symbols to query (defaults to all symbols) -

    Returns:
        Complete SQL query string
    """
    # SELECT clause
    select_clause = select_sql(columns)

    # FROM clause
    from_clause = f" FROM {table_name}"

    # WHERE clause
    where_clause = where_sql_multiple(filters, filter_merge, universe)

    # ORDER BY clause
    order_clause = order_by_sql(sort_fields)

    # LIMIT and OFFSET clause
    limit_clause = limit_offset_sql(limit, offset)

    return f"SELECT{select_clause}{from_clause}{where_clause}{order_clause}{limit_clause};"


def select_sql(columns: list[str] = None) -> str:
    """Generate SELECT clause"""
    if not columns:
        return " *"

    # Quote column names to handle special characters/keywords
    quoted_columns = [f'"{col}"' for col in columns]
    return f" {', '.join(quoted_columns)}"


def where_sql_multiple(filters: list[dict[str, Any]] = None,
                       filter_merge: str = "AND",
                       universe: list[str] | None = None
                       ) -> str:
    """Generate WHERE clause from multiple filters"""

    where_conditions = []

    # Handle universe filter
    if universe is not None:
        if len(universe) == 0:
            # Empty universe - return no results
            return " WHERE 1=2"
        else:
            # Add universe filter
            universe_list = "', '".join(universe)
            where_conditions.append(f"ticker IN ('{universe_list}')")

    # Handle other filters
    if filters:
        filter_clauses = []
        for filter_dict in filters:
            clause = where_sql(filter_dict)
            if clause:
                # Remove the " WHERE " prefix if it exists
                clause = clause.replace(" WHERE ", "")
                filter_clauses.append(clause)

        if filter_clauses:
            # Combine filter clauses with the specified merge operator
            if len(filter_clauses) == 1:
                where_conditions.append(filter_clauses[0])
            else:
                combined_filters = f" {filter_merge} ".join(filter_clauses)
                where_conditions.append(f"({combined_filters})")

    if not where_conditions:
        return ""

    # Always join multiple conditions with AND
    return f" WHERE {' AND '.join(where_conditions)}"


def where_sql(filter: dict[str, Any]) -> str:
    """Generate WHERE clause from single filter"""
    if not filter or not filter.get('type'):
        return ""

    grid_clause = generate_where_clause_from_advanced_filter(filter)
    return grid_clause if grid_clause else ""


def generate_where_clause_from_advanced_filter(filter: dict[str, Any]) -> str:
    """Generate WHERE clause from advanced filter model"""
    if filter.get('filterType') == 'join':
        conditions = filter.get('conditions', [])
        parts = [generate_where_clause_from_advanced_filter(condition)
                 for condition in conditions]
        parts = [part for part in parts if part]  # Filter out empty strings
        join_type = filter.get('type', 'AND')
        return f"({f' {join_type} '.join(parts)})"

    return base_filter_to_sql(filter)


def base_filter_to_sql(filter_dict: dict[str, Any]) -> str:
    """Convert base filter to SQL"""
    col = f'"{filter_dict["colId"]}"'
    val = escape_value(filter_dict.get('filter'))
    filter_type = filter_dict.get('type')

    if filter_type == 'contains':
        return f"{col} LIKE '%' || {val} || '%'"
    elif filter_type == 'notContains':
        return f"{col} NOT LIKE '%' || {val} || '%'"
    elif filter_type == 'equals':
        return f"{col} = {val}"
    elif filter_type == 'notEqual':
        return f"{col} != {val}"
    elif filter_type == 'startsWith':
        return f"{col} LIKE {val} || '%'"
    elif filter_type == 'endsWith':
        return f"{col} LIKE '%' || {val}"
    elif filter_type == 'blank':
        return f"({col} IS NULL OR {col} = '')"
    elif filter_type == 'notBlank':
        return f"({col} IS NOT NULL AND {col} != '')"
    elif filter_type == 'greaterThan':
        return f"{col} > {val}"
    elif filter_type == 'greaterThanOrEqual':
        return f"{col} >= {val}"
    elif filter_type == 'lessThan':
        return f"{col} < {val}"
    elif filter_type == 'lessThanOrEqual':
        return f"{col} <= {val}"
    elif filter_type == 'true':
        return f"{col} = TRUE"
    elif filter_type == 'false':
        return f"{col} = FALSE"
    else:
        raise ValueError(f"Unsupported filter type: {filter_type}")


def order_by_sql(sort_fields: list[dict[str, str]] = None) -> str:
    """
    Generate ORDER BY clause

    Args:
        sort_fields: List of dictionaries with 'field' and 'direction' keys
                    direction should be 'ASC' or 'DESC'
    """
    if not sort_fields:
        return ""

    sort_clauses = []
    for sort_field in sort_fields:
        field = sort_field.get('colId')
        direction = sort_field.get('sort', 'asc').upper()

        if field:
            # Validate direction
            if direction not in ['ASC', 'DESC']:
                direction = 'ASC'
            sort_clauses.append(f'"{field}" {direction}')

    if not sort_clauses:
        return ""

    return f" ORDER BY {', '.join(sort_clauses)}"


def limit_offset_sql(limit: int | None = None, offset: int | None = None) -> str:
    """Generate LIMIT and OFFSET clause"""
    parts = []

    if offset is not None:
        parts.append(f"OFFSET {offset}")

    if limit is not None:
        parts.append(f"LIMIT {limit}")

    return f" {' '.join(parts)}" if parts else ""


def escape_value(value: Any) -> str:
    """Escape SQL values"""
    if isinstance(value, str):
        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)
