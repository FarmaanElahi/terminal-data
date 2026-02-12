from pydantic import BaseModel


class ScreenerQuery(BaseModel):
    query: str


class ScreenerResponse(BaseModel):
    result: list[dict]
