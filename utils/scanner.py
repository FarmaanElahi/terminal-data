import pandas as pd

from utils.fundamentals import get_fundamentals
from utils.industry import get_industry_classification
from utils.pandas_utils import merge_df_safely
from utils.rating import get_ratings
from utils.technical import get_technicals
from utils.tradingview import TradingView
from utils.pandas_utils import make_df_ready_for_serialization
from utils.bucket import storage_options, data_bucket
from logging import Logger

logger = Logger(__name__)


async def run_full_scanner_build():
    logger.info("Running full scanner build")

    df = TradingView.get_base_symbols(1000)
    logger.info("Base Symbols loaded")

    index_df = await  TradingView.get_index(df.columns)
    logger.info("Index loaded")

    df = pd.concat([df, index_df])
    logger.info("Final symbols generated")

    df = merge_df_safely(df, get_industry_classification())
    logger.info("Industry classification updated")

    df = merge_df_safely(df, get_fundamentals())
    logger.info("Fundamentals updated")

    df = merge_df_safely(df, await get_technicals(df, df.index.to_list()))
    logger.info("Technicals updated")

    df = merge_df_safely(df, get_ratings(df))
    logger.info("Rating updated")

    df = make_df_ready_for_serialization(df)
    logger.info("Prepare for serialization")

    df.to_parquet(f'oci://{data_bucket}/symbols-full-v2.parquet', compression='zstd', storage_options=storage_options)
    logger.info("Scanner build complete")
