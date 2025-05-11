import pandas as pd
import numpy as np


def to_datetime(series: pd.Series, unit='s', utc=True):
    return pd.to_datetime(series.astype('Int64'), unit=unit)


# Safely access DataFrame index
def safe_iloc(dataframe, column, index, default=None):
    try:
        if index < len(dataframe) and column in dataframe.columns:
            value = dataframe[column].iloc[index]
            # Check if the value is None, NaN, or an empty string
            if pd.isna(value) or value == '':
                return default
            return value
        return default
    except:
        return default


def merge_df_safely(src: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    merged = src.copy().merge(other, left_index=True, right_index=True, how='left', suffixes=('', '_new'))

    # Loop through columns in df2
    for col in other.columns:
        new_col = f'{col}_new'
        if col in src.columns:
            # Overwrite only where df2 has non-null values
            merged[col] = merged[new_col].combine_first(merged[col])
            # Drop the extra merged column
            merged.drop(columns=[new_col], inplace=True)
        else:
            # New column, already added by merge, nothing to do
            pass

    return merged


def make_df_ready_for_serialization(df: pd.DataFrame):
    df: pd.DataFrame = df.copy()
    for col in df.columns:
        # Replace NaN with None for PostgreSQL compatibility
        df[col] = df[col].where(pd.notnull(df[col]), None)

    df = df.replace('nan', None)
    df = df.replace([np.inf, -np.inf], None)
    return df