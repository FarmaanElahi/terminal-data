import pytest
from sqlmodel import Session, create_engine, SQLModel
from terminal.lists.service import ListService
from terminal.lists.enums import ListType


@pytest.fixture(name="session")
def session_fixture():
    # Use SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_list(session: Session):
    lst = ListService.create_list(session, "My List", ListType.simple)
    assert lst.id is not None
    assert lst.name == "My List"
    assert lst.type == ListType.simple


def test_append_symbols(session: Session):
    lst = ListService.create_list(session, "Simple", ListType.simple)
    ListService.append_symbols(session, lst.id, ["AAPL", "GOOG"])

    lst = ListService.get_list(session, lst.id)
    assert "AAPL" in lst.symbols
    assert "GOOG" in lst.symbols
    assert len(lst.symbols) == 2


def test_bulk_remove_symbols(session: Session):
    lst = ListService.create_list(session, "Simple", ListType.simple)
    ListService.append_symbols(session, lst.id, ["AAPL", "GOOG", "TSLA"])
    ListService.bulk_remove_symbols(session, lst.id, ["AAPL", "TSLA"])

    lst = ListService.get_list(session, lst.id)
    assert lst.symbols == ["GOOG"]


def test_unique_color_list_constraint(session: Session):
    red = ListService.create_list(session, "Red", ListType.color, color="red")
    green = ListService.create_list(session, "Green", ListType.color, color="green")

    # Add AAPL to Red
    ListService.append_symbols(session, red.id, ["AAPL"])
    assert "AAPL" in ListService.get_symbols(session, red.id)

    # Add AAPL to Green (should remove from Red)
    ListService.append_symbols(session, green.id, ["AAPL"])

    assert "AAPL" not in ListService.get_symbols(session, red.id)
    assert "AAPL" in ListService.get_symbols(session, green.id)


def test_combo_list_aggregation(session: Session):
    l1 = ListService.create_list(session, "L1", ListType.simple)
    l2 = ListService.create_list(session, "L2", ListType.simple)

    ListService.append_symbols(session, l1.id, ["S1", "S2"])
    ListService.append_symbols(session, l2.id, ["S2", "S3"])

    combo = ListService.create_list(
        session, "Combo", ListType.combo, source_list_ids=[l1.id, l2.id]
    )

    symbols = ListService.get_symbols(session, combo.id)
    assert set(symbols) == {"S1", "S2", "S3"}
