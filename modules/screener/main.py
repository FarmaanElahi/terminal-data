import tempfile

import aiohttp
import duckdb
import pandas as pd
from duckdb.duckdb import DuckDBPyConnection
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel


class ScreenerQuery(BaseModel):
    query: str


class ScreenerResponse(BaseModel):
    result: list[dict]


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PARQUET_URL = "https://objectstorage.ap-hyderabad-1.oraclecloud.com/n/axbaetdfzydd/b/terminal-files/o/symbols-full-v2.parquet"
cached_df: pd.DataFrame = None  # Will hold the data in memory


async def download_parquet(url: str) -> str:
    """Download the Parquet file to a temporary location."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
            temp_file.write(await response.read())
            temp_file.close()
            return temp_file.name


con:DuckDBPyConnection
@app.on_event("startup")
async def load_data_on_startup():
    global cached_df
    cached_df = pd.read_parquet(PARQUET_URL)
    cached_df.reset_index(inplace=True)
    global con
    con = duckdb.connect()
    con.register("data", cached_df)  # Expose as a table named 'data'
    print("✅ Parquet data loaded into memory.")


@app.post("/query")
async def query_data(q: ScreenerQuery):
    """Run a custom SQL query on the cached data."""
    global cached_df
    if cached_df is None:
        return JSONResponse(content={"error": "Data not yet loaded."}, status_code=503)

    try:
        query = q.query.replace(f"""'{PARQUET_URL}'""", 'data')
        result_df = con.execute(query).fetchdf()
        return Response(content=result_df.to_json(orient="records"), media_type="application/json")
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
