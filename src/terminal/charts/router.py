from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
def list_study_templates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return service.list_study_templates(session, current_user.id)


@router.post("/study-templates", response_model=StudyTemplateMeta)
def upsert_study_template(
    data: StudyTemplateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return service.upsert_study_template(session, current_user.id, data)


@router.get("/study-templates/{name}/content")
def get_study_template_content(
    name: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    template = service.get_study_template(session, current_user.id, name)
    if not template:
        raise HTTPException(status_code=404, detail="Study template not found")
    return template


@router.delete("/study-templates/{name}", status_code=204)
def delete_study_template(
    name: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    template = service.get_study_template(session, current_user.id, name)
    if not template:
        raise HTTPException(status_code=404, detail="Study template not found")
    service.delete_study_template(session, template)


# ─── Chart routes ──────────────────────────────────────────────────────────────


@router.get("", response_model=list[ChartMeta])
def list_charts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return service.list_charts(session, current_user.id)


@router.post("", response_model=ChartMeta)
def create_chart(
    data: ChartCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return service.create_chart(session, current_user.id, data)


@router.get("/{chart_id}/content", response_model=ChartPublic)
def get_chart_content(
    chart_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return chart


@router.put("/{chart_id}", response_model=ChartMeta)
def update_chart(
    chart_id: str,
    data: ChartUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    return service.update_chart(session, chart, data)


@router.delete("/{chart_id}", status_code=204)
def delete_chart(
    chart_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    chart = service.get_chart(session, chart_id, current_user.id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")
    service.delete_chart(session, chart)
