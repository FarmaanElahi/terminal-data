import pytest
from sqlmodel import Session
from terminal.lists import service as lists_service
from terminal.lists.models import (
    ListCreate,
    ListUpdate,
    SymbolsUpdate,
    SourceListsUpdate,
)
from terminal.lists.enums import ListType

from terminal.auth.models import User

USER_ID = "test-user-id"
OTHER_USER_ID = "other-user-id"


@pytest.fixture(autouse=True)
def setup_users(session: Session):
    """Seed users for foreign key constraints."""
    if not session.get(User, USER_ID):
        session.add(User(id=USER_ID, username="testuser", hashed_password="..."))
    if not session.get(User, OTHER_USER_ID):
        session.add(User(id=OTHER_USER_ID, username="otheruser", hashed_password="..."))
    session.commit()


def test_create_list(session: Session):
    data = ListCreate(name="My List", type=ListType.simple)
    lst = lists_service.create(session, USER_ID, data)
    assert lst.name == "My List"
    assert lst.user_id == USER_ID
    assert lst.type == ListType.simple


def test_get_list(session: Session):
    data = ListCreate(name="My List", type=ListType.simple)
    lst = lists_service.create(session, USER_ID, data)
    fetched = lists_service.get(session, lst.id, user_id=USER_ID)
    assert fetched.id == lst.id


def test_get_all_lists(session: Session):
    lists_service.create(session, USER_ID, ListCreate(name="L1", type=ListType.simple))
    lists_service.create(session, USER_ID, ListCreate(name="L2", type=ListType.simple))
    all_lists = lists_service.all(session, USER_ID)
    assert len(all_lists) == 2


def test_append_symbols_simple(session: Session):
    data = ListCreate(name="Simple", type=ListType.simple)
    lst = lists_service.create(session, USER_ID, data)

    lists_service.append_symbols(session, lst, USER_ID, SymbolsUpdate(symbols=["AAPL"]))

    assert lst.symbols == ["AAPL"]


def test_color_list_exclusive_symbols(session: Session):
    # Two color lists for same user
    l1 = lists_service.create(
        session, USER_ID, ListCreate(name="Red", type=ListType.color, color="red")
    )
    l2 = lists_service.create(
        session, USER_ID, ListCreate(name="Blue", type=ListType.color, color="blue")
    )

    # Add symbol to Red
    lists_service.append_symbols(session, l1, USER_ID, SymbolsUpdate(symbols=["AAPL"]))
    assert "AAPL" in l1.symbols

    # Add same symbol to Blue -> should be removed from Red
    lists_service.append_symbols(
        session, l2, USER_ID, SymbolsUpdate(symbols=["AAPL", "MSFT"])
    )
    assert "AAPL" in l2.symbols
    assert "AAPL" not in l1.symbols


def test_combo_symbols_aggregation(session: Session):
    # Create source lists
    s1 = lists_service.create(
        session, USER_ID, ListCreate(name="S1", type=ListType.simple)
    )
    s2 = lists_service.create(
        session, USER_ID, ListCreate(name="S2", type=ListType.simple)
    )

    lists_service.append_symbols(session, s1, USER_ID, SymbolsUpdate(symbols=["AAPL"]))
    lists_service.append_symbols(session, s2, USER_ID, SymbolsUpdate(symbols=["MSFT"]))

    # Create combo list
    combo = lists_service.create(
        session,
        USER_ID,
        ListCreate(name="Combo", type=ListType.combo, source_list_ids=[s1.id, s2.id]),
    )

    symbols = lists_service.get_symbols(session, combo, USER_ID)
    assert set(symbols) == {"AAPL", "MSFT"}


def test_cross_user_security(session: Session):
    # User 1 creates a list
    l1 = lists_service.create(
        session, USER_ID, ListCreate(name="U1 List", type=ListType.simple)
    )

    # User 2 tries to fetch it -> should be None
    fetched = lists_service.get(session, l1.id, user_id=OTHER_USER_ID)
    assert fetched is None

    # User 2's all should be empty
    assert lists_service.all(session, OTHER_USER_ID) == []


def test_combo_source_list_management(session: Session):
    l1 = lists_service.create(
        session, USER_ID, ListCreate(name="L1", type=ListType.simple)
    )
    l2 = lists_service.create(
        session, USER_ID, ListCreate(name="L2", type=ListType.simple)
    )

    combo = lists_service.create(
        session,
        USER_ID,
        ListCreate(name="Combo", type=ListType.combo, source_list_ids=[l1.id]),
    )

    # Append
    lists_service.append_source_lists(
        session, combo, SourceListsUpdate(source_list_ids=[l2.id])
    )
    assert set(combo.source_list_ids) == {l1.id, l2.id}

    # Remove
    lists_service.bulk_remove_source_lists(
        session, combo, SourceListsUpdate(source_list_ids=[l1.id])
    )
    assert combo.source_list_ids == [l2.id]


def test_update_list(session: Session):
    lst = lists_service.create(
        session, USER_ID, ListCreate(name="Old Name", type=ListType.simple)
    )
    updated = lists_service.update(session, lst, ListUpdate(name="New Name"))

    assert updated.name == "New Name"
    assert lists_service.get(session, lst.id, USER_ID).name == "New Name"
