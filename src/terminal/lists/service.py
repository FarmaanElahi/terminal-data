from sqlalchemy.orm import Session
from sqlalchemy import select
from terminal.lists.models import (
    List,
    ListCreate,
    ListUpdate,
    SymbolsUpdate,
    SourceListsUpdate,
)
from terminal.lists.enums import ListType


def get(session: Session, list_id: str, user_id: str | None = None) -> List | None:
    """Get list by ID, optionally filtered by user_id."""
    statement = select(List).where(List.id == list_id)
    if user_id:
        statement = statement.where(List.user_id == user_id)
    return session.execute(statement).scalars().first()


def get_all(session: Session, user_id: str) -> list[List]:
    """Get all lists for a user."""
    return list(
        session.execute(select(List).where(List.user_id == user_id)).scalars().all()
    )


def ensure_default_lists(session: Session, user_id: str):
    """Ensure default COLOR lists exist for the user."""
    # Check if any COLOR lists exist
    existing = (
        session.execute(
            select(List).where(List.user_id == user_id, List.type == ListType.color)
        )
        .scalars()
        .first()
    )

    if not existing:
        defaults = [
            ("Red", "red"),
            ("Green", "green"),
            ("Yellow", "yellow"),
            ("Blue", "blue"),
            ("Purple", "purple"),
        ]
        for name, color in defaults:
            lst = List(
                user_id=user_id,
                name=name,
                type=ListType.color,
                color=color,
            )
            session.add(lst)
        session.commit()


def create(
    session: Session,
    user_id: str,
    data: ListCreate,
) -> List:
    """Create a new list for a user."""
    lst = List(
        user_id=user_id,
        name=data.name,
        type=data.type,
        color=data.color,
        source_list_ids=data.source_list_ids or [],
    )
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def update(session: Session, lst: List, data: ListUpdate) -> List:
    """Update list attributes using schema."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lst, key, value)

    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def append_symbols(
    session: Session, lst: List, user_id: str, data: SymbolsUpdate
) -> List:
    """Append symbols to a list."""
    # If it's a COLOR list, ensure symbols are removed from other COLOR lists for the same user
    if lst.type == ListType.color:
        color_lists = (
            session.execute(
                select(List).where(
                    List.type == ListType.color,
                    List.user_id == user_id,
                    List.id != lst.id,
                )
            )
            .scalars()
            .all()
        )
        for other_lst in color_lists:
            other_lst.symbols = [s for s in other_lst.symbols if s not in data.symbols]
            session.add(other_lst)

    # Add symbols to the current list, avoiding duplicates
    existing_symbols = set(lst.symbols)
    for s in data.symbols:
        existing_symbols.add(s)

    lst.symbols = list(existing_symbols)
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def bulk_remove_symbols(session: Session, lst: List, data: SymbolsUpdate) -> List:
    """Bulk remove symbols."""
    lst.symbols = [s for s in lst.symbols if s not in data.symbols]
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def append_source_lists(session: Session, lst: List, data: SourceListsUpdate) -> List:
    """Append source list IDs to a COMBO list."""
    existing_ids = set(lst.source_list_ids)
    for lid in data.source_list_ids:
        existing_ids.add(lid)

    lst.source_list_ids = list(existing_ids)
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def bulk_remove_source_lists(
    session: Session, lst: List, data: SourceListsUpdate
) -> List:
    """Bulk remove source list IDs from a COMBO list."""
    lst.source_list_ids = [
        lid for lid in lst.source_list_ids if lid not in data.source_list_ids
    ]
    session.add(lst)
    session.commit()
    session.refresh(lst)
    return lst


def get_symbols(session: Session, lst: List, user_id: str) -> list[str]:
    """Get symbols for a list, aggregating for COMBO lists."""
    if lst.type == ListType.combo:
        # Aggregate symbols from all source lists owned by the same user
        all_symbols = set()
        source_lists = (
            session.execute(
                select(List).where(
                    List.id.in_(lst.source_list_ids), List.user_id == user_id
                )
            )
            .scalars()
            .all()
        )
        for sl in source_lists:
            all_symbols.update(sl.symbols)
        return list(all_symbols)

    return lst.symbols
