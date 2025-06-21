import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from utils.bucket import storage_options, data_bucket


def fetch_website_data():
    url = 'https://halalstock.in/halal-shariah-compliant-shares-list/'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept-Language': 'en-IN,en;q=0.9',
        'Cache-Control': 'no-cache'
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def extract_first_table_data(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Find the first table on the page
    table = soup.find('table')
    if not table:
        raise ValueError("No table found on the page.")

    data = []

    rows = table.find('tbody').find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 5:
            continue

        # Determine shariah compliance status
        img_tag = cells[0].find('img')
        if img_tag:
            src = img_tag.get('src', '').lower()
            if 'yes.jpg' in src:
                compliant = 'Yes'
            elif 'no.jpg' in src:
                compliant = 'No'
            else:
                compliant = 'Unknown'
        else:
            compliant = 'Unknown'

        bse_raw = cells[2].text.strip()
        nse_raw = cells[3].text.strip()
        bse_symbol = f"BSE:{bse_raw}" if bse_raw else np.nan
        nse_symbol = f"NSE:{nse_raw}" if nse_raw else np.nan

        data.append([bse_symbol, nse_symbol, compliant])

    return data


def refresh_compliant():
    html = fetch_website_data()
    data = extract_first_table_data(html)
    df = pd.DataFrame(data, columns=['bse_symbol', 'nse_symbol', 'shariah_compliant'])
    df = df[df['nse_symbol'].notna() & (df['nse_symbol'].str.strip() != '')]
    df.set_index('nse_symbol', inplace=True)
    df = df[~df.index.duplicated(keep='first')]
    df.to_parquet(f'oci://{data_bucket}/shariah-compliant.parquet', compression='zstd', storage_options=storage_options)


def shariah_compliant_symbols():
    df = pd.read_parquet(f'oci://{data_bucket}/shariah-compliant.parquet', storage_options=storage_options)
    return df[['shariah_compliant']]
