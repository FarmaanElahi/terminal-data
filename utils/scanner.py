import pandas as pd

from utils.bucket import storage_options, data_bucket
from utils.fundamentals import get_fundamentals
from utils.industry import get_industry_classification
from utils.pandas_utils import make_df_ready_for_serialization
from utils.pandas_utils import merge_df_safely
from utils.rating import get_ratings
from utils.technical import get_technicals
from utils.tradingview import TradingView


async def run_full_scanner_build():
    print("Running full scanner build")

    df = TradingView.get_base_symbols(100)
    print("Base Symbols loaded")

    index_df = await  TradingView.get_index(df.columns)
    print("Index loaded")

    df = pd.concat([df, index_df])
    print("Final symbols generated")

    df = merge_df_safely(df, get_industry_classification())
    print("Industry classification updated")

    df = merge_df_safely(df, get_fundamentals())
    print("Fundamentals updated")

    df = merge_df_safely(df, await get_technicals(df, df.index.to_list()))
    print("Technicals updated")

    df = merge_df_safely(df, get_ratings(df))
    print("Rating updated")

    df = make_df_ready_for_serialization(df)
    print("Prepare for serialization")

    df.to_parquet(f'oci://{data_bucket}/symbols-full-v2.parquet', compression='zstd', storage_options=storage_options)
    print("Scanner build complete")
