import pandas as pd


def get_ratings(df: pd.DataFrame):
    df = as_rating(df)
    df = rs_rating(df)
    df = sector_industry_strength_rating(df)
    df = momentum_rating(df)
    return df


def compute_rating(series: pd.Series):
    # Rank stocks, convert to percentile (0-1), scale to 1-99
    percentile = series.rank(pct=True)  # Gives values between 0 and 1
    asr = percentile * 98 + 1  # Scale to 1-99
    return asr.fillna(1).round().astype(int)  # Round to integer

def momentum_rating(df: pd.DataFrame):
    df = df.copy()
    df['momentum_rating'] = compute_rating(df['momentum'])
    # momentum_acc_{period}D
    for period in [5,10,15,20,21]:
        df[f'momentum_acc_{period}D_rating'] = compute_rating(df[f'momentum_acc_{period}D'])
    return df

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


import pandas as pd


def sector_industry_strength_rating(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes group strength rankings based on median returns for valid symbols.

    - For each timeframe (e.g. 3M), filters symbols with price_volume over 1 Cr
    - Excludes type != 'stock'
    - Requires groups with ≥ 2 valid symbols for ranking
    - Computes return for all groups, but ranks only valid ones

    Returns:
        pd.DataFrame with *_ranking_<timeframe>, *_return_<timeframe> columns.
    """
    df = df.copy()
    min_mcap = 1 * 10 ** 10  # 1000 Cr
    min_liquidity = 25 * 10 ** 7  # 1 Cr

    perf_cols = [
        "price_perf_1D", "price_perf_1W", "price_perf_2W", "price_perf_1M",
        "price_perf_3M", "price_perf_6M", "price_perf_9M", "price_perf_12M"
    ]

    volume_map = {
        "1D": "price_volume",
        "1W": "price_volume_sma_5D",
        "2W": "price_volume_sma_10D",
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

            # Compute return for all groups
            return_col = f"{group_col}_return_{timeframe}"
            all_group_median = df_all.groupby(group_col)[perf_col].median().rename(return_col)

            # Filter valid rows for ranking
            valid_df = df_all[
                (df_all["mcap"] >= min_mcap) &
                (df_all["type"].str.lower() == "stock") &
                (df_all[volume_col] > min_liquidity)
                ].copy()

            # Get valid groups with at least 2 symbols
            group_counts = valid_df[group_col].value_counts()
            valid_groups = group_counts[group_counts >= 2].index
            valid_df = valid_df[valid_df[group_col].isin(valid_groups)]

            # Compute ranking only for valid groups
            valid_group_median = valid_df.groupby(group_col)[perf_col].median()
            group_rank = valid_group_median.rank(method='min', ascending=False).astype(pd.Int64Dtype())

            # Fill in missing ranks for other groups with max rank + 1
            max_rank = group_rank.max()
            all_ranks = pd.Series(max_rank + 1, index=all_group_median.index, name=f"{group_col}_ranking_{timeframe}")
            all_ranks.update(group_rank)

            result_dict[return_col] = all_group_median
            result_dict[all_ranks.name] = all_ranks.astype(pd.Int64Dtype())

        return pd.concat(result_dict.values(), axis=1)

    def merge_group_info(df_base, group_col):
        group_metrics = compute_group_rankings(df_base, group_col)
        df_merged = df_base.merge(group_metrics, how='left', left_on=group_col, right_index=True)
        return df_merged

    # Apply to each group level
    df_result = df.copy()
    for group_col in ['sector', 'industry', 'sub_industry', 'industry_2']:
        df_result = merge_group_info(df_result, group_col)

    return df_result
