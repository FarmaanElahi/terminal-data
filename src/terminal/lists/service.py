from sqlmodel import Session, select
from terminal.lists.models import List
from terminal.lists.enums import ListType
from fastapi import HTTPException


class ListService:
    @staticmethod
    def get_list(session: Session, list_id: str) -> List:
        lst = session.get(List, list_id)
        if not lst:
            raise HTTPException(status_code=404, detail="List not found")
        return lst

    @staticmethod
    def create_list(
        session: Session,
        name: str,
        list_type: ListType,
        color: str = None,
        source_list_ids: list[str] = None,
    ) -> List:
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

    @staticmethod
    def get_all_lists(session: Session) -> list[List]:
        return session.exec(select(List)).all()

    @staticmethod
    def append_symbols(session: Session, list_id: str, symbols: list[str]) -> List:
        lst = ListService.get_list(session, list_id)

        if lst.type == ListType.combo:
            raise HTTPException(
                status_code=400, detail="Cannot append symbols to a COMBO list"
            )

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

    @staticmethod
    def bulk_remove_symbols(session: Session, list_id: str, symbols: list[str]) -> List:
        lst = ListService.get_list(session, list_id)

        if lst.type == ListType.combo:
            raise HTTPException(
                status_code=400, detail="Cannot remove symbols from a COMBO list"
            )

        lst.symbols = [s for s in lst.symbols if s not in symbols]
        session.add(lst)
        session.commit()
        session.refresh(lst)
        return lst

    @staticmethod
    def get_symbols(session: Session, list_id: str) -> list[str]:
        lst = ListService.get_list(session, list_id)

        if lst.type == ListType.combo:
            # Aggregate symbols from all source lists
            all_symbols = set()
            source_lists = session.exec(
                select(List).where(List.id.in_(lst.source_list_ids))
            ).all()  # type: ignore
            for sl in source_lists:
                # Recursively get symbols? The requirement says "collection of simple lists"
                # so we assume source_list_ids only contains SIMPLE lists.
                all_symbols.update(sl.symbols)
            return list(all_symbols)

        return lst.symbols
