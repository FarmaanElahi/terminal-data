from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from terminal.charts.models import (
    UserChart,
    UserStudyTemplate,
    ChartCreate,
    ChartUpdate,
    StudyTemplateCreate,
)


async def list_charts(session: AsyncSession, user_id: str) -> list[UserChart]:
    return list(
        (await session.execute(
            select(UserChart).where(UserChart.user_id == user_id)
        )).scalars().all()
    )


async def get_chart(session: AsyncSession, chart_id: str, user_id: str) -> UserChart | None:
    return (await session.execute(
        select(UserChart).where(
            UserChart.id == chart_id, UserChart.user_id == user_id
        )
    )).scalars().first()


async def create_chart(session: AsyncSession, user_id: str, data: ChartCreate) -> UserChart:
    chart = UserChart(
        user_id=user_id,
        name=data.name,
        symbol=data.symbol,
        resolution=data.resolution,
        content=data.content,
    )
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    return chart


async def update_chart(session: AsyncSession, chart: UserChart, data: ChartUpdate) -> UserChart:
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chart, key, value)
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    return chart


async def delete_chart(session: AsyncSession, chart: UserChart) -> None:
    await session.delete(chart)
    await session.commit()


async def list_study_templates(session: AsyncSession, user_id: str) -> list[UserStudyTemplate]:
    return list(
        (await session.execute(
            select(UserStudyTemplate).where(UserStudyTemplate.user_id == user_id)
        )).scalars().all()
    )


async def get_study_template(
    session: AsyncSession, user_id: str, name: str
) -> UserStudyTemplate | None:
    return (await session.execute(
        select(UserStudyTemplate).where(
            UserStudyTemplate.user_id == user_id, UserStudyTemplate.name == name
        )
    )).scalars().first()


async def upsert_study_template(
    session: AsyncSession, user_id: str, data: StudyTemplateCreate
) -> UserStudyTemplate:
    existing = await get_study_template(session, user_id, data.name)
    if existing:
        existing.content = data.content
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing
    template = UserStudyTemplate(
        user_id=user_id, name=data.name, content=data.content
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def delete_study_template(session: AsyncSession, template: UserStudyTemplate) -> None:
    await session.delete(template)
    await session.commit()
