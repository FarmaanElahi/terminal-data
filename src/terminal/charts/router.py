from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.dependencies import get_session
from terminal.charts import service
from terminal.charts.models import (
    ChartCreate,
    ChartUpdate,
    ChartMeta,
    ChartPublic,
    StudyTemplateCreate,
    StudyTemplateMeta,
)

router = APIRouter(prefix="/charts", tags=["Charts"])

# ─── Study template routes (declared before /{chart_id} to avoid path conflicts) ─────

@router.get("/study-templates", response_model=list[StudyTemplateMeta])
async def list_study_templates(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.list_study_templates(session, current_user.id)


@router.post("/study-templates", response_model=StudyTemplateMeta)
async def upsert_study_template(
    data: StudyTemplateCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.upsert_study_template(session, current_user.id, data)


@router.get("/study-templates/{name}/content")
async def get_study_template_content(
    name: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    template = await service.get_study_template(session, current_user.id, name)
    if not template:
        raise HTTPException(status_code=404, detail="Study template not found")
    return template


@router.delete("/study-templates/{name}", status_code=204)
async def delete_study_template(
    name: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    template = await service.get_study_template(session, current_user.id, name)
    if not template:
        raise HTTPException(status_code=404, detail="Study template not found")
    await service.delete_study_template(session, template)


# ─── Chart routes ──────────────────────────────────────────────────────────────


@router.get("", response_model=list[ChartMeta])
async def list_charts(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.list_charts(session, current_user.id)


@router.post("", response_model=ChartMeta)
async def create_chart(
    data: ChartCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await service.create_chart(session, current_user.id, data)


@router.get("/{chart_id}/content", response_model=ChartPublic)
async def get_chart_content(
    chart_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = await service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return chart


@router.put("/{chart_id}", response_model=ChartMeta)
async def update_chart(
    chart_id: str,
    data: ChartUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = await service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return await service.update_chart(session, chart, data)


@router.delete("/{chart_id}", status_code=204)
async def delete_chart(
    chart_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = await service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    await service.delete_chart(session, chart)
