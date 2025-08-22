from typing import List
from pydantic import BaseModel


class ScanResponse(BaseModel):
    """
    Response model for scan results.

    Attributes:
        columns: List of column names
         List of rows, where each row is a list of values
    """
    columns: List[str]
    data: List[List]
