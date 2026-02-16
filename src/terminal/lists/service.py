from typing import Optional
from sqlmodel import Session, select
from terminal.lists.models import List
from terminal.lists.enums import ListType


def get(session: Session, list_id: str) -> Optional[List]:
    """Get list by ID or return None."""
    return session.get(List, list_id)


def create(
    session: Session,
    name: str,
    list_type: ListType,
    color: Optional[str] = None,
    source_list_ids: Optional[list[str]] = None,
) -> List:
    """Create a new list."""
    lst = List(
        name=name,
        type=list_type,
        color=color,
        source_list_ids=source_list_ids or [],
    )
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def append_symbols(
    session: Session, list_id: str, symbols: list[str]
) -> Optional[List]:
    """Append symbols to a list. Returns None if list not found or is COMBO."""
    lst = get(session, list_id)
    if not lst or lst.type == ListType.combo:
        return None

    # If it's a COLOR list, ensure symbols are removed from other COLOR lists
    if lst.type == ListType.color:
        color_lists = session.exec(
            select(List).where(List.type == ListType.color, List.id != list_id)
        ).all()
        for other_lst in color_lists:
            other_lst.symbols = [s for s in other_lst.symbols if s not in symbols]
            session.add(other_lst)

    # Add symbols to the current list, avoiding duplicates
    existing_symbols = set(lst.symbols)
    for s in symbols:
        existing_symbols.add(s)

    lst.symbols = list(existing_symbols)
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def bulk_remove_symbols(
    session: Session, list_id: str, symbols: list[str]
) -> Optional[List]:
    """Bulk remove symbols. Returns None if list not found or is COMBO."""
    lst = get(session, list_id)
    if not lst or lst.type == ListType.combo:
        return None

    lst.symbols = [s for s in lst.symbols if s not in symbols]
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def get_symbols(session: Session, list_id: str) -> list[str]:
    """Get symbols for a list, aggregating for COMBO lists."""
    lst = session.get(List, list_id)
    if not lst:
        return []

    if lst.type == ListType.combo:
        # Aggregate symbols from all source lists
        all_symbols = set()
        source_lists = session.exec(
            select(List).where(List.id.in_(lst.source_list_ids))
        ).all()  # type: ignore
        for sl in source_lists:
            all_symbols.update(sl.symbols)
        return list(all_symbols)

    return lst.symbols
