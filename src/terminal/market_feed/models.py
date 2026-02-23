from pydantic import BaseModel


class MarketFeedRefreshResponse(BaseModel):
    status: str
    count: int
    message: str
