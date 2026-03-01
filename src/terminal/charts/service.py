from sqlalchemy.orm import Session
from sqlalchemy import select
from terminal.charts.models import (
    UserChart,
    UserStudyTemplate,
    ChartCreate,
    ChartUpdate,
    StudyTemplateCreate,
)


def list_charts(session: Session, user_id: str) -> list[UserChart]:
    return list(
        session.execute(
            select(UserChart).where(UserChart.user_id == user_id)
        ).scalars().all()
    )


def get_chart(session: Session, chart_id: str, user_id: str) -> UserChart | None:
    return session.execute(
        select(UserChart).where(
            UserChart.id == chart_id, UserChart.user_id == user_id
        )
    ).scalars().first()


def create_chart(session: Session, user_id: str, data: ChartCreate) -> UserChart:
    chart = UserChart(
        user_id=user_id,
        name=data.name,
        symbol=data.symbol,
        resolution=data.resolution,
        content=data.content,
    )
    session.add(chart)
    session.commit()
    session.refresh(chart)
    return chart


def update_chart(session: Session, chart: UserChart, data: ChartUpdate) -> UserChart:
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chart, key, value)
    session.add(chart)
    session.commit()
    session.refresh(chart)
    return chart


def delete_chart(session: Session, chart: UserChart) -> None:
    session.delete(chart)
    session.commit()


def list_study_templates(session: Session, user_id: str) -> list[UserStudyTemplate]:
    return list(
        session.execute(
            select(UserStudyTemplate).where(UserStudyTemplate.user_id == user_id)
        ).scalars().all()
    )


def get_study_template(
    session: Session, user_id: str, name: str
) -> UserStudyTemplate | None:
    return session.execute(
        select(UserStudyTemplate).where(
            UserStudyTemplate.user_id == user_id, UserStudyTemplate.name == name
        )
    ).scalars().first()


def upsert_study_template(
    session: Session, user_id: str, data: StudyTemplateCreate
) -> UserStudyTemplate:
    existing = get_study_template(session, user_id, data.name)
    if existing:
        existing.content = data.content
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    template = UserStudyTemplate(
        user_id=user_id, name=data.name, content=data.content
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def delete_study_template(session: Session, template: UserStudyTemplate) -> None:
    session.delete(template)
    session.commit()
