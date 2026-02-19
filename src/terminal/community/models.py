from typing import Literal, Union
from terminal.models import TerminalBase


class GlobalFeedParam(TerminalBase):
    feed: Literal["trending", "suggested", "popular"]
    limit: int


class SymbolFeedParam(TerminalBase):
    feed: Literal["symbol"]
    filter: Literal["trending", "popular"]
    symbol: str
    limit: int


Param = Union[GlobalFeedParam, SymbolFeedParam]
