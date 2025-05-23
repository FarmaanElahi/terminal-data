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


def close_con():
    if _con is not None:
        _con.close()
