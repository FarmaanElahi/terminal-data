import requests
from bs4 import BeautifulSoup
import pandas as pd

# URL of the webpage
url = 'https://shner-elmo.github.io/TradingView-Screener/fields/stocks.html'

# Send a GET request
response = requests.get(url)
response.raise_for_status()

# Parse the HTML content
soup = BeautifulSoup(response.text, 'html.parser')

# Find the table
table = soup.find('table')

# Initialize a list to store extracted data
columns = []

# Iterate over each row in the table body
for row in table.tbody.find_all('tr'):
    cells = row.find_all('td')

    if len(cells) == 3:
        # Extract display name and type
        display_name = cells[1].get_text(strip=True)
        column_type = cells[2].get_text(strip=True)

        # Check if the first cell contains a <details> tag
        details = cells[0].find('details')
        if details:
            # Extract all variations from the <li> elements inside <ul>
            variations = [li.get_text(strip=True) for li in details.find_all('li')]
        else:
            # Otherwise, just extract the plain text
            variations = [cells[0].get_text(strip=True)]

        # Store all variations
        for var in variations:
            columns.append({
                'Column Name': var,
                'Display Name': display_name,
                'Type': column_type
            })
    else:
        print(f"Unexpected row format: {row}")

# Convert the extracted data to a DataFrame for better visualization
df = pd.DataFrame(columns)

df.to_csv('fields.csv',index=False)
