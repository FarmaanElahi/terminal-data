import json
from datetime import datetime
from typing import Any

import pandas as pd

from utils.bucket import data_bucket, data_bucket_fs


def get_fundamentals():
    with data_bucket_fs.open(f'{data_bucket}/fundamental.json', 'rb') as f:
        funda_json: list[dict[str, Any]] = json.loads(f.read())
        fundamental_metrics = []
        for row in funda_json:
            row_data = row["data"]
            ticker = row_data['companyId']
            quarterly = row_data["quarterly"]
            yearly = row_data["yearly"]
            fq = flatten_quarterly(quarterly)
            fy = flatten_yearly(yearly)
            fundamental_metrics.append({"ticker": ticker, "quarterly": quarterly, "yearly": yearly, **fq, **fy})

        funda = pd.DataFrame(fundamental_metrics)
        funda.latest_available_quarter = funda['latest_available_quarter'].astype('category')
        funda.set_index(["ticker"], inplace=True)
        funda.quarterly = funda.quarterly.apply(json.dumps)
        funda.yearly = funda.yearly.apply(json.dumps)
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
        for i in range(1, 13):
            quarter_idx = i - 1
            column_name = f"{new_name}_fq_{i}"

            if quarter_idx < len(df):
                result_dict[column_name] = df[original_name].iloc[quarter_idx]
            else:
                result_dict[column_name] = None

    return result_dict


def flatten_yearly(data, in_crores=True):
    """
    Flatten stock metrics data to easily access current and historical values.

    The function transforms yearly metrics data into a dictionary where:
    - TTM metrics (last row) use _ttm suffix (for specific metrics only)
    - Current fiscal year metrics use _fy_1 suffix
    - Previous fiscal years use _fy_2, _fy_3, etc.

    Args:
        data: A list of lists containing stock metrics, where first row is column names and subsequent rows are values
        in_crores: Boolean indicating if the currency values are in crores (multiplier = 10^7)

    Returns:
        A dictionary with flattened metrics
    """
    # Initialize an empty result dictionary
    result = {}
    max_loopback = 6

    # Define which metrics should have TTM values
    ttm_metrics = [
        'Revenue', 'Revenue Growth', 'OPM', 'PAT', 'PAT Growth',
        'NPM', 'EPS', 'EPS Growth'
    ]

    # Mapping of original metric names to our flattened keys
    metrics_to_extract = {
        'Revenue': 'revenue', 'Revenue Growth': 'revenue_growth',
        'Operating Profit': 'operating_profit', 'OPM': 'opm',
        'NPM': 'npm', 'PAT': 'pat', 'PAT Growth': 'pat_growth',
        'EPS': 'eps', 'EPS Growth': 'eps_growth', 'ROA': 'roa',
        'ROE': 'roe', 'ROCE': 'roce', 'GPM': 'gpm',
        'Debt To Equity': 'debt_to_equity', 'Current Ratio': 'current_ratio'
    }

    # Metrics that should be treated as currency values (to expand if in crores)
    currency_metrics = [
        'Revenue', 'Expenses', 'Employee Cost', 'Material Cost', 'Manufacturing Cost',
        'Operating Profit', 'Other Income', 'Interest Expense', 'Exceptional Items',
        'Depreciation', 'PBT', 'Tax', 'PAT', 'Equity Capital', 'Reserves',
        'Deposits', 'Borrowings', 'Long Term Borrowings', 'Short Term Borrowings',
        'Lease Liabilities Current', 'Lease Liabilities Non Current',
        'Property Plant and Equipment', 'Current Liabilities', 'Non Current Liabilities',
        'Trade Payables', 'Total Liabilities', 'Investments', 'Advances',
        'Non Current Assets', 'Current Assets', 'Right of Use Assets', 'CWIP',
        'Inventories', 'Trade Receivables', 'Cash Equivalents', 'Fixed Assets',
        'Total Assets', 'Operating Cash Flow', 'Working Capital Changes',
        'Investing Cash Flow', 'Fixed Assets Purchased', 'Fixed Assets Sold',
        'Investments Purchased', 'Investments Sold', 'Interest Received',
        'Dividends Received', 'Financing Cash Flow', 'Tax Paid', 'Interest Paid',
        'Dividends Paid', 'Net Cash Flow', 'Free Cash Flow', 'Market Capitalization',
        'EBIT'
    ]

    # Initialize all potential keys with None to ensure data consistency
    for metric, key in metrics_to_extract.items():
        # For TTM metrics
        if metric in ttm_metrics:
            result[f"{key}_ttm"] = None

        # For fiscal year metrics (up to 10 years back)
        for i in range(1, max_loopback + 1):
            result[f"{key}_fy_{i}"] = None

    # If data is empty or has only headers, return initialized dictionary with None values
    if not data or len(data) < 2:
        return result

    # Extract column names and find indices for relevant metrics
    columns = data[0]
    date_index = columns.index("Date") if "Date" in columns else 0

    # Get indices for all metrics we want to extract
    metric_indices = {}
    for metric in metrics_to_extract:
        if metric in columns:
            metric_indices[metric] = columns.index(metric)

    # Get indices for currency metrics (for expansion)
    currency_indices = {}
    for metric in currency_metrics:
        if metric in columns:
            currency_indices[metric] = columns.index(metric)

    # Create a copy of the data to avoid modifying the original
    data_copy = [row[:] for row in data]

    # Expand currency values if needed
    if in_crores:
        for row in data_copy[1:]:  # Skip the header row
            for metric, idx in currency_indices.items():
                # Only expand if the value is not None or empty string
                if idx < len(row) and row[idx] not in (None, "", "null"):
                    try:
                        # Multiply by 10^7 to convert crores to actual value
                        row[idx] = float(row[idx]) * 10000000
                    except (ValueError, TypeError):
                        # If conversion fails, leave the value as is
                        pass

    # Extract fiscal year data (all rows except header and potentially TTM)
    fiscal_years = sorted(data_copy[1:-1], key=lambda x: x[date_index], reverse=True)

    # Always treat the last row as TTM data, regardless of what's in the date column
    ttm_data = data_copy[-1]

    # Extract TTM values for specific metrics from the last row
    # Only if we have at least 4 rows of data (header + 3 fiscal years + TTM)
    if len(data_copy) >= 5:
        for metric in ttm_metrics:
            if metric in metric_indices:
                metric_key = metrics_to_extract[metric]
                ttm_value = ttm_data[metric_indices[metric]]
                result[f"{metric_key}_ttm"] = ttm_value

    # Extract fiscal year values
    for i, year_data in enumerate(fiscal_years, 1):
        if i > max_loopback:  # Limit to 10 years
            break

        for metric, key in metrics_to_extract.items():
            if metric in metric_indices:
                value = year_data[metric_indices[metric]]
                result[f"{key}_fy_{i}"] = value

    return result


def get_latest_completed_quarter():
    """
    Determine the latest completed quarter based on current date.
    Financial quarters end in March (03), June (06), September (09), and December (12).
    Format: YYYYMM where YYYY is the fiscal year and MM is the month.
    """
    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year

    # Determine the last completed quarter
    if current_month < 4:  # Jan, Feb, Mar
        # Last quarter was Dec of previous year
        quarter_month = 12
        quarter_year = current_year - 1
    elif current_month < 7:  # Apr, May, Jun
        # Last quarter was Mar of current year
        quarter_month = 3
        quarter_year = current_year
    elif current_month < 10:  # Jul, Aug, Sep
        # Last quarter was Jun of current year
        quarter_month = 6
        quarter_year = current_year
    else:  # Oct, Nov, Dec
        # Last quarter was Sep of current year
        quarter_month = 9
        quarter_year = current_year

    # Format as YYYYMM
    return f"{quarter_year}{quarter_month:02d}"


def flatten_quarterly(data, latest_quarter=None, in_crores=True):
    """
    Flatten quarterly metrics data for easy access to current and historical values.

    Args:
        data: A list of lists with quarterly metrics, where first row contains column names
        latest_quarter: Optional string indicating the latest completed quarter (e.g., "202503")
                       If None, automatically determines the latest completed quarter
        in_crores: Boolean indicating if the currency values are in crores (multiplier = 10^7)

    Returns:
        A dictionary with flattened metrics
    """
    # Initialize an empty result dictionary
    result = {}
    max_loopback = 6

    # Determine latest quarter if not specified
    if latest_quarter is None:
        latest_quarter = get_latest_completed_quarter()

    # Store the latest quarter value in the result
    result["latest_quarter"] = latest_quarter

    # Mapping of original metric names to our flattened keys
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

    # Metrics that should be treated as currency values (to expand if in crores)
    currency_metrics = [
        'Revenue', 'Expenses', 'Employee Cost', 'Material Cost',
        'Operating Profit', 'Other Income', 'Interest Expense',
        'Depreciation', 'PBT', 'Tax', 'PAT'
    ]

    # Initialize all potential keys with None to ensure data consistency
    for _, key in metrics.items():
        # For latest quarter metrics
        result[f"{key}_fq_latest"] = None

        # For quarterly metrics (up to 20 quarters back)
        for i in range(1, max_loopback + 1):
            result[f"{key}_fq_{i}"] = None

    # If data is empty or has only headers, return initialized dictionary with None values
    if not data or len(data) < 2:
        return result

    # Extract column names and find indices for relevant metrics
    columns = data[0]
    date_index = columns.index("Date") if "Date" in columns else 0

    # Get indices for all metrics we want to extract
    metric_indices = {}
    for metric in metrics:
        if metric in columns:
            metric_indices[metric] = columns.index(metric)

    # Get indices for currency metrics (for expansion)
    currency_indices = {}
    for metric in currency_metrics:
        if metric in columns:
            currency_indices[metric] = columns.index(metric)

    # Get all quarters excluding header
    quarters = data[1:]

    # Sort quarters in descending order (newest first)
    quarters = sorted(quarters, key=lambda x: x[date_index], reverse=True)

    # Expand currency values if needed
    if in_crores:
        for quarter_data in quarters:
            for metric, idx in currency_indices.items():
                # Only expand if the value is not None or empty string
                if idx < len(quarter_data) and quarter_data[idx] not in (None, ""):
                    try:
                        # Multiply by 10^7 to convert crores to actual value
                        quarter_data[idx] = float(quarter_data[idx]) * 10000000
                    except (ValueError, TypeError):
                        # If conversion fails, leave the value as is
                        pass

    # Store the latest available quarter in the data
    result["latest_available_quarter"] = quarters[0][date_index] if quarters else None

    # Find the most recent quarter that matches or doesn't exceed the specified latest_quarter
    latest_quarter_data = None
    for quarter in quarters:
        if quarter[date_index] <= latest_quarter:
            latest_quarter_data = quarter
            break

    # If found, use this quarter for _fq_latest values
    if latest_quarter_data:
        # Only use this quarter as the latest if it actually matches the latest quarter
        # Otherwise, leave the _fq_latest values as None
        if latest_quarter_data[date_index] == latest_quarter:
            for metric, key in metrics.items():
                if metric in metric_indices:
                    idx = metric_indices[metric]
                    result[f"{key}_fq_latest"] = latest_quarter_data[idx]
        # Note: if the dates don't match, we keep _fq_latest values as None

    # Extract quarterly values for historical data
    for i, quarter_data in enumerate(quarters, 1):
        if i > max_loopback:  # Limit to 20 quarters
            break

        for metric, key in metrics.items():
            if metric in metric_indices:
                idx = metric_indices[metric]
                result[f"{key}_fq_{i}"] = quarter_data[idx]

    return result
