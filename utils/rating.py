import pandas as pd


def get_ratings(df: pd.DataFrame):
    df = as_rating(df)
    df = rs_rating(df)
    df = sector_industry_strength_rating(df)
    return df


def compute_rating(series: pd.Series):
    # Rank stocks, convert to percentile (0-1), scale to 1-99
    percentile = series.rank(pct=True)  # Gives values between 0 and 1
    asr = percentile * 98 + 1  # Scale to 1-99
    return asr.fillna(1).round().astype(int)  # Round to integer


def as_rating(df: pd.DataFrame):
    df = df.copy()
    # Rank should  be between 1 to 99
    df['AS_Rating_1D'] = compute_rating(df['price_perf_1D'])
    df['AS_Rating_1W'] = compute_rating(df['price_perf_1W'])
    df['AS_Rating_1M'] = compute_rating(df['price_perf_1M'])
    df['AS_Rating_3M'] = compute_rating(df['price_perf_3M'])
    df['AS_Rating_6M'] = compute_rating(df['price_perf_6M'])
    df['AS_Rating_9M'] = compute_rating(df['price_perf_9M'])
    df['AS_Rating_12M'] = compute_rating(df['price_perf_12M'])
    return df


def rs_rating(df: pd.DataFrame):
    df = df.copy()
    df['RS_Rating_1D'] = compute_rating(df['RS_Value_1D'])
    df['RS_Rating_1W'] = compute_rating(df['RS_Value_1W'])
    df['RS_Rating_1M'] = compute_rating(df['RS_Value_1M'])
    df['RS_Rating_3M'] = compute_rating(df['RS_Value_3M'])
    df['RS_Rating_6M'] = compute_rating(df['RS_Value_6M'])
    df['RS_Rating_9M'] = compute_rating(df['RS_Value_9M'])
    df['RS_Rating_12M'] = compute_rating(df['RS_Value_12M'])
    return df


def sector_industry_strength_rating(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes group strength rankings based on median returns for valid symbols.

    - For each timeframe (e.g. 3M), filters symbols with price_volume over 1 Cr
    - Excludes type == 'stock'
    - Requires groups with ≥ 2 valid symbols
    - Adds ranking and return columns for each group (sector, industry, etc.)

    Returns:
        pd.DataFrame with *_ranking_<timeframe>, *_return_<timeframe> columns.
    """
    df = df.copy()
    min_liquidity = 1 * 10 ** 7  # 1 Cr

    perf_cols = [
        "price_perf_1D", "price_perf_1W", "price_perf_1M",
        "price_perf_3M", "price_perf_6M", "price_perf_9M", "price_perf_12M"
    ]

    volume_map = {
        "1D": "price_volume",
        "1W": "price_volume_sma_5D",
        "1M": "price_volume_sma_21D",
        "3M": "price_volume_sma_63D",
        "6M": "price_volume_sma_126D",
        "9M": "price_volume_sma_189D",
        "12M": "price_volume_sma_252D"
    }

    def compute_group_rankings(df_all, group_col):
        result_dict = {}

        for perf_col in perf_cols:
            timeframe = perf_col.split('_')[-1]
            volume_col = volume_map.get(timeframe)
            if volume_col not in df_all.columns:
                continue

            valid_df = df_all[
                (df_all["type"].str.lower() == "stock") &
                (df_all[volume_col] > min_liquidity)
            ].copy()

            group_counts = valid_df[group_col].value_counts()
            valid_groups = group_counts[group_counts >= 2].index
            valid_df = valid_df[valid_df[group_col].isin(valid_groups)]

            return_col = f"{group_col}_return_{timeframe}"
            rank_col = f"{group_col}_ranking_{timeframe}"

            group_median = valid_df.groupby(group_col)[perf_col].median().rename(return_col)
            group_rank = group_median.rank(method='min', ascending=False).astype(pd.Int64Dtype()).rename(rank_col)

            result_dict[return_col] = group_median
            result_dict[rank_col] = group_rank

        return pd.concat(result_dict.values(), axis=1)

    def merge_group_info(df_base, group_col):
        group_metrics = compute_group_rankings(df_base, group_col)
        df_merged = df_base.merge(group_metrics, how='left', left_on=group_col, right_index=True)
        return df_merged

    # Apply to each group level
    df_result = df.copy()
    for group_col in ['sector', 'industry', 'sub_industry', 'industry_2']:
        df_result = merge_group_info(df_result, group_col)

    # Fill missing values
    for group_col in ['sector', 'industry', 'sub_industry', 'industry_2']:
        for col in df_result.columns:
            if col.startswith(f"{group_col}_return_"):
                df_result[col] = df_result[col].fillna(-9999)
            elif col.startswith(f"{group_col}_ranking_"):
                df_result[col] = df_result[col].fillna(9999).astype(pd.Int64Dtype())

    return df_result