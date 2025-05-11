import pandas as pd
from utils.bucket import storage_options, data_bucket


def get_classification():
    # Download the nse industry
    classification_df = pd.read_csv(f'oci://{data_bucket}/nse_industry_symbols.csv', storage_options=storage_options)
    classification_df['ticker'] = "NSE:" + classification_df["Symbol"]
    classification_df = classification_df.drop(columns=["Symbol"])
    classification_df = classification_df.rename(
        columns={"Sector": "sector", "Industry": "industry", "Basic Industry": "sub_industry", "Macro": "macro_sector"})
    classification_df = classification_df.set_index(["ticker"])
    classification_df.sector = classification_df['sector'].astype('category')
    classification_df.industry = classification_df['industry'].astype('category')
    classification_df.sub_industry = classification_df['sub_industry'].astype('category')
    classification_df.macro_sector = classification_df['macro_sector'].astype('category')

    return classification_df
