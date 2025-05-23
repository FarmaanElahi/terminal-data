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
    Computes group strength rankings using top-N performers per timeframe in each group.

    - For each timeframe (e.g. 3M), selects top-N symbols within each group
      by that timeframe's return, and computes median group return.
    - Top-N per group:
        - sector: 50
        - industry: 20
        - industry_2: 20
        - sub_industry: 10
    - Rankings are assigned only if:
        - symbol is of type 'stock'
        - mcap >= 100 Cr
        - group has ≥ 2 valid symbols
    - Returns are computed for all symbols in all groups.
    - Adds momentum column (e.g. sector_momentum) with values:
        - 'strengthening', 'weakening', 'stable'

    Returns:
        pd.DataFrame with *_ranking_<timeframe>, *_return_<timeframe>,
        and *_momentum columns.
    """
    df = df.copy()
    min_mcap = 100 * 10 ** 8  # 1000 Cr

    perf_cols = [
        "price_perf_1D", "price_perf_1W", "price_perf_1M",
        "price_perf_3M", "price_perf_6M", "price_perf_9M", "price_perf_12M"
    ]

    group_top_n = {
        'sector': 50,
        'industry': 20,
        'sub_industry': 10,
        'industry_2': 20
    }

    def compute_group_rankings_by_timeframe(df_all, group_col, top_n):
        df_ranking_base = df_all[
            (df_all["mcap"] >= min_mcap) &
            (df_all["type"].str.lower() == "stock")
            ].copy()

        group_counts = df_ranking_base[group_col].value_counts()
        valid_groups = group_counts[group_counts > 1].index
        df_ranking_base = df_ranking_base[df_ranking_base[group_col].isin(valid_groups)]

        group_ranks = {}

        for col in perf_cols:
            timeframe = col.split('_')[-1]
            return_col = f"{group_col}_return_{timeframe}"
            rank_col = f"{group_col}_ranking_{timeframe}"

            df_top_n = (
                df_ranking_base.sort_values(col, ascending=False)
                .groupby(group_col)
                .head(top_n)
            )

            group_median = df_top_n.groupby(group_col)[col].median().rename(return_col)
            group_rank = group_median.rank(method='min', ascending=False).astype(pd.Int64Dtype()).rename(rank_col)

            group_ranks[return_col] = group_median
            group_ranks[rank_col] = group_rank

        return pd.concat(group_ranks.values(), axis=1)

    def compute_group_returns_all(df_all, group_col):
        group_returns = {}

        for col in perf_cols:
            timeframe = col.split('_')[-1]
            return_col = f"{group_col}_return_{timeframe}"

            group_median = df_all.groupby(group_col)[col].median().rename(return_col)
            group_returns[return_col] = group_median

        return pd.concat(group_returns.values(), axis=1)

    def merge_group_data(df_base, group_col, top_n):
        ranking_df = compute_group_rankings_by_timeframe(df_base, group_col, top_n)
        df_merged = df_base.merge(ranking_df, how='left', left_on=group_col, right_index=True)

        return_df = compute_group_returns_all(df_base, group_col)
        overlapping = [col for col in return_df.columns if col in df_merged.columns]
        df_merged = df_merged.drop(columns=overlapping, errors='ignore')
        df_merged = df_merged.merge(return_df, how='left', left_on=group_col, right_index=True)

        return df_merged

    df_ranked = df.copy()
    for group_col in ['sector', 'industry', 'sub_industry','industry_2']:
        df_ranked = merge_group_data(df_ranked, group_col, group_top_n[group_col])

    # Fill missing values
    for group_col in ['sector', 'industry', 'sub_industry','industry_2']:
        for col in df_ranked.columns:
            if col.startswith(f"{group_col}_return_"):
                df_ranked[col] = df_ranked[col].fillna(-9999)
            elif col.startswith(f"{group_col}_ranking_"):
                df_ranked[col] = df_ranked[col].fillna(9999).astype(pd.Int64Dtype())

    return df_ranked
