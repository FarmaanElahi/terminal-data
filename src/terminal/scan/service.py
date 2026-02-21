from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from terminal.scan.models import (
    Scan,
    ScanCreate,
    ScanUpdate,
)


def all(session: Session, user_id: str) -> list[Scan]:
    return list(
        session.execute(select(Scan).where(Scan.user_id == user_id)).scalars().all()
    )


def get(session: Session, user_id: str, scan_id: str) -> Scan | None:
    return (
        session.execute(select(Scan).where(Scan.user_id == user_id, Scan.id == scan_id))
        .scalars()
        .first()
    )


def create(session: Session, user_id: str, scan_in: ScanCreate) -> Scan:
    scan = Scan(
        id=str(uuid4()),
        user_id=user_id,
        name=scan_in.name,
        source=scan_in.source,
        conditions=[c.model_dump() for c in scan_in.conditions],
        conditional_logic=scan_in.conditional_logic,
        columns=[c.model_dump() for c in scan_in.columns],
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def update(
    session: Session, user_id: str, scan_id: str, scan_in: ScanUpdate
) -> Scan | None:
    scan = get(session, user_id, scan_id)
    if not scan:
        return None

    update_data = scan_in.model_dump(exclude_unset=True)
    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [
            c if isinstance(c, dict) else dict(c) for c in update_data["conditions"]
        ]
    if "columns" in update_data and update_data["columns"] is not None:
        update_data["columns"] = [
            c if isinstance(c, dict) else dict(c) for c in update_data["columns"]
        ]

    for field, value in update_data.items():
        setattr(scan, field, value)

    session.commit()
    session.refresh(scan)
    return scan


def delete(session: Session, user_id: str, scan_id: str) -> bool:
    scan = get(session, user_id, scan_id)
    if not scan:
        return False

    session.delete(scan)
    session.commit()
    return True
