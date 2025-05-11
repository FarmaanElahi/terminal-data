import pandas as pd


def to_datetime(series: pd.Series, unit='s', utc=True):
    return pd.to_datetime(series.astype('Int64'), unit=unit)
