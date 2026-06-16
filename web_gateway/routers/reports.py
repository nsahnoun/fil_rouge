import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.database import get_db
from ..core.dependencies import get_current_user, require_role
from ..core.exceptions import NotFoundException
from ..models import Analysis, Report, ReportTemplate, User

router = APIRouter(dependencies=[Depends(get_current_user)])


# ── Templates ─────────────────────────────────────────────────────
@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReportTemplate).order_by(ReportTemplate.name))
    templates = result.scalars().all()
    return [{"id": t.id, "name": t.name, "description": t.description, "is_default": t.is_default} for t in templates]


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    template_html: str
    template_css: str | None = None
    is_default: bool = False


@router.post("/templates")
async def create_template(
    req: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("settings", "*")),
):
    tmpl = ReportTemplate(
        name=req.name,
        description=req.description,
        template_html=req.template_html,
        template_css=req.template_css,
        is_default=req.is_default,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.flush()
    return {"id": tmpl.id, "name": tmpl.name}


# ── Canvas export (PNG, JSON, PDF from analysis canvas) ──────────
class CanvasExportRequest(BaseModel):
    analysis_id: int
    export_type: str  # png, json, pdf
    file_data: str  # base64


@router.post("/canvas-export")
async def canvas_export(
    req: CanvasExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Analysis).where(Analysis.id == req.analysis_id).options(selectinload(Analysis.radio))
    )
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    patient_id = a.radio.patient_id
    ext = req.export_type
    filename = f"canvas_export_{uuid.uuid4().hex[:8]}.{ext}"
    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    file_path = report_dir / filename
    raw = base64.b64decode(req.file_data)
    file_path.write_bytes(raw)
    report = Report(
        patient_id=patient_id,
        analysis_id=req.analysis_id,
        generated_by=current_user.id,
        report_type=f"canvas_{ext}",
        file_path=str(file_path),
        file_size=len(raw),
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.flush()
    return {"id": report.id, "filename": filename, "status": "saved"}


# ── Reports ───────────────────────────────────────────────────────
class GenerateReportRequest(BaseModel):
    patient_id: int
    analysis_id: int | None = None
    report_type: str = "clinical"
    template_id: int | None = None


@router.post("/generate")
async def generate_report(
    req: GenerateReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("reports", "create")),
):
    if req.template_id:
        tmpl = await db.execute(select(ReportTemplate).where(ReportTemplate.id == req.template_id))
        if not tmpl.scalar_one_or_none():
            raise NotFoundException("Template introuvable")
    report = Report(
        patient_id=req.patient_id,
        analysis_id=req.analysis_id,
        generated_by=current_user.id,
        report_type=req.report_type,
        template_id=req.template_id,
    )
    db.add(report)
    await db.flush()
    return {"id": report.id, "status": "generated"}


@router.get("/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Rapport introuvable")
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "analysis_id": r.analysis_id,
        "report_type": r.report_type,
        "file_path": r.file_path,
        "file_size": r.file_size,
        "is_sent": r.is_sent,
        "signed_by": r.signed_by,
        "signed_at": r.signed_at,
        "created_at": r.created_at,
    }


@router.get("/{report_id}/download")
async def download_report(report_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Rapport introuvable")
    if not r.file_path or not Path(r.file_path).exists():
        raise NotFoundException("Fichier introuvable")
    media_type = {
        "canvas_png": "image/png",
        "canvas_pdf": "application/pdf",
        "canvas_json": "application/json",
    }.get(r.report_type, "application/octet-stream")
    return FileResponse(r.file_path, media_type=media_type, filename=Path(r.file_path).name)


@router.post("/{report_id}/sign")
async def sign_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("reports", "sign")),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Rapport introuvable")
    from datetime import datetime, timezone
    r.signed_by = current_user.id
    r.signed_at = datetime.now(timezone.utc)
    r.digital_signature = f"signed-{current_user.id}-{report_id}"
    await db.flush()
    return {"status": "signed"}
