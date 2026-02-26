from terminal.models import TerminalBase


class SymbolCreate(TerminalBase):
    ticker: str
    name: str
    type: str
    market: str
    isin: str | None = None
    indexes: list[dict[str, str]] = []
    typespecs: list[str] = []
    logo: str | None = None


class SymbolSearchResultItem(TerminalBase):
    ticker: str
    name: str
    type: str
    market: str
    typespecs: list[str] = []
    logo: str | None = None


class SearchResultResponse(TerminalBase):
    items: list[SymbolSearchResultItem]
