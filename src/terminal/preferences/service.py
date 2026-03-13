from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from terminal.preferences.models import UserPreferences, PreferencesUpdate
from terminal.models import uuid7_str


async def get(session: AsyncSession, user_id: str) -> UserPreferences | None:
    return (await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )).scalars().first()


async def upsert(session: AsyncSession, user_id: str, data: PreferencesUpdate) -> UserPreferences:
    """Insert or update user preferences using PostgreSQL ON CONFLICT DO UPDATE."""
    now = datetime.now(timezone.utc)

    stmt = pg_insert(UserPreferences).values(
        id=uuid7_str(),
        user_id=user_id,
        layout=data.layout,
        settings=data.settings,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_preferences_user_id",
        set_={
            "layout": stmt.excluded.layout,
            "settings": stmt.excluded.settings,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await session.execute(stmt)
    await session.commit()

    return (await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )).scalars().first()
