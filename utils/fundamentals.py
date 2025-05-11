import json

import pandas as pd

from utils.bucket import data_bucket, data_bucket_fs


def get_fundamentals():
    with data_bucket_fs.open(f'{data_bucket}@/fundamental.json', 'rb') as f:
        funda_json = json.loads(f.read())
        fundamental_metrics = []
        for row in funda_json:
            row_data = row["data"]
            ticker = row_data['companyId']
            quarterly = row_data["quarterly"]
            yearly = row_data["yearly"]
            quarterly_result = extract_quarterly_result(quarterly[1:], columns=quarterly[0])
            yearly_pnl = extract_pnl(yearly[1:], columns=yearly[0])
            fundamental_metrics.append({"ticker": ticker, "quarterly": quarterly, "yearly": yearly, **yearly_pnl, **quarterly_result})

        funda = pd.DataFrame(fundamental_metrics)
        funda.set_index(["ticker"], inplace=True)
        return funda


def extract_quarterly_result(data: list, columns: list[str]):
    # Create DataFrame
    df = pd.DataFrame(data, columns=columns)

    df['Date'] = pd.to_datetime(df['Date'], format='%Y%m').dt.strftime('%Y-%m')
    df = df.set_index(['Date'])

    # Sort by date (most recent first)
    df = df.sort_values('Date', ascending=False).reset_index(drop=True)

    # Define the metrics we want to extract and their formatted names
    metrics = {
        'Revenue': 'revenue',
        'Revenue Growth YoY': 'revenue_growth_yoy',
        'Revenue Growth QoQ': 'revenue_growth_qoq',
        'OPM': 'opm',
        'NPM': 'npm',
        'PAT': 'pat',
        'PAT Growth YoY': 'pat_growth_yoy',
        'PAT Growth QoQ': 'pat_growth_qoq',
        'EPS': 'eps',
        'EPS Growth YoY': 'eps_growth_yoy',
        'EPS Growth QoQ': 'eps_growth_qoq'
    }

    # Create a dictionary to hold the data
    result_dict = {}

    # Fill the dictionary with metric values
    for original_name, new_name in metrics.items():
        for i in range(1, 7):
            quarter_idx = i - 1
            column_name = f"{new_name}_fq_{i}"

            if quarter_idx < len(df):
                result_dict[column_name] = df[original_name].iloc[quarter_idx]
            else:
                result_dict[column_name] = None

    return result_dict


def extract_pnl(data: list, columns: list[str]):
    # Create DataFrame
    df = pd.DataFrame(data, columns=columns)

    # Handle TTM as the latest period
    # Sort by date but put TTM at the beginning if it exists
    ttm_row = None
    regular_rows = []

    for i, row in df.iterrows():
        if row['Date'] == 'TTM':
            ttm_row = row
        else:
            regular_rows.append(row)

    # Sort regular rows by date (most recent first)
    # Convert YYYYMM to a sortable format
    sorted_rows = sorted(regular_rows, key=lambda x: x['Date'], reverse=True)

    # Reconstruct the DataFrame with TTM first if it exists
    if ttm_row is not None:
        sorted_data = [ttm_row] + sorted_rows
    else:
        sorted_data = sorted_rows

    # Create a new DataFrame with the sorted data
    df_sorted = pd.DataFrame(sorted_data, columns=columns)

    # Define the metrics we want to extract
    metrics = {
        'Revenue': 'revenue',
        'Revenue Growth': 'revenue_growth',
        'OPM': 'opm',
        'NPM': 'npm',
        'PAT': 'pat',
        'PAT Growth': 'pat_growth',
        'EPS': 'eps',
        'EPS Growth': 'eps_growth',
        'ROA': 'roa',
        'ROE': 'roe',
        'ROCE': 'roce',
        'GPM': 'gpm',
        'Debt To Equity': 'debt_to_equity',
        'Net Cash Flow': 'net_cash_flow',
    }

    # Create a dictionary to hold the data
    result_dict = {}

    # Fill the dictionary with metric values
    for original_name, new_name in metrics.items():
        for i in range(1, 6):
            quarter_idx = i - 1
            column_name = f"{new_name}_fy_{i}"

            if quarter_idx < len(df_sorted):
                result_dict[column_name] = df_sorted[original_name].iloc[quarter_idx]
            else:
                result_dict[column_name] = None

    return result_dict
