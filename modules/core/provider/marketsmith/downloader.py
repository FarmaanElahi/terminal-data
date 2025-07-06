import asyncio

import pandas as pd

from modules.core.provider.marketsmith.client import MarketSmithClient
from utils.bucket import storage_options, data_bucket


class MarketSmithDownloader:
    def __init__(self, max_clients=10):
        self.max_clients = max_clients
        self.failed = []
        self.results = []
        self.client_queue = None

    async def init_clients(self):
        """Initialize the client pool"""
        self.client_queue = asyncio.Queue()
        for _ in range(self.max_clients):
            client = MarketSmithClient()
            await client.init_session()
            await self.client_queue.put(client)
        return self.client_queue

    async def fetch_data(self, ticker, row):
        """Fetch data for a single ticker using available client from pool"""
        search_term = row['name']

        # Skip invalid search terms
        if "." in search_term:
            self.results.append({"ticker": ticker, "data": None})
            return

        # Get client from queue (waits if none available)
        client = await self.client_queue.get()

        try:
            data = await client.all(search_term)
            self.results.append({"ticker": ticker, "data": data})
        except Exception as e:
            print(f"Failed to load {ticker}: {e}")
            self.failed.append(ticker)
            self.results.append({"ticker": ticker, "data": None})  # Ensure None value for failed downloads
        finally:
            # Always return client to queue
            await self.client_queue.put(client)

    async def download_all(self, symbols_df: pd.DataFrame):
        """Main method to download all symbols with parallel processing"""
        # Initialize client pool
        await self.init_clients()

        # Create tasks for all symbols
        tasks = [
            self.fetch_data(ticker, row)
            for ticker, row in symbols_df.iterrows()
        ]

        # Execute all tasks concurrently
        await asyncio.gather(*tasks)

        # Return results as DataFrame
        df = pd.DataFrame(self.results)
        df.set_index('ticker', inplace=True)
        df.to_parquet(f'oci://{data_bucket}/ms_india_data.parquet', compression='zstd', storage_options=storage_options)
        return df

    @staticmethod
    def get_extracted():
        data =  pd.read_parquet(f'oci://{data_bucket}/ms_india_data.parquet', storage_options=storage_options)

        df = pd.DataFrame([], columns=['ms_buyer_demand', 'ms_master_score', 'ms_rs_rating', 'ms_eps_rank', 'ms_industry_group_rank', 'ms_earning_stability'])
        df.ms_buyer_demand = data.apply(lambda row: row.data['details']['detailsGeneralInformationHeader']["accDisRating"] if row.data is not None else None,
                                     axis=1)
        df.ms_master_score = data.apply(lambda row: row.data['details']['detailsGeneralInformationHeader']["masterScore"] if row.data is not None else None,
                                     axis=1)
        df.ms_rs_rating = data.apply(lambda row: row.data['details']['detailsGeneralInformationHeader']["rsNumericGrade"] if row.data is not None else None,
                                  axis=1)
        df.ms_eps_rank = data.apply(lambda row: row.data['details']['detailsGeneralInformationHeader']["epsRank"] if row.data is not None else None, axis=1)
        df.ms_industry_group_rank = data.apply(
            lambda row: row.data['details']['detailsGeneralInformationHeader']["industryGroupRank"] if row.data is not None else None, axis=1)
        df.ms_earning_stability = data.apply(
            lambda row: row.data['details']['detailsGeneralInformationHeaderBlock']["earningsStability"] if row.data is not None else None, axis=1)

        return df

    async def cleanup(self):
        """Clean up client connections"""
        if self.client_queue:
            clients = []
            while not self.client_queue.empty():
                client = await self.client_queue.get()
                clients.append(client)

            # Close all client sessions
            for client in clients:
                if hasattr(client, 'close'):
                    await client.close()
