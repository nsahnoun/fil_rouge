import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings as app_settings
from ..core.database import get_db
from ..core.dependencies import require_role
from ..models import Analysis, AuditLog, ClinicSetting, Patient, Report, User
from ..services.ceph_client import ceph_client_override_url

router = APIRouter(dependencies=[Depends(require_role("settings", "*"))])


class UpdateSettingRequest(BaseModel):
    key: str
    value: str


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClinicSetting))
    overrides = {s.setting_key: s.setting_value for s in result.scalars().all()}
    return {
        "clinic_name": overrides.get("clinic_name", app_settings.clinic_name),
        "clinic_city": overrides.get("clinic_city", app_settings.clinic_city),
        "clinic_address": overrides.get("clinic_address", ""),
        "ceph_api_url": overrides.get("ceph_api_url", app_settings.ceph_api_url),
    }


@router.put("/settings")
async def update_setting(
    req: UpdateSettingRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ClinicSetting).where(ClinicSetting.setting_key == req.key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.setting_value = req.value
    else:
        setting = ClinicSetting(setting_key=req.key, setting_value=req.value)
        db.add(setting)
    await db.flush()
    if req.key == "ceph_api_url":
        ceph_client_override_url(req.value)
    return {"status": "updated", "key": req.key, "value": req.value}


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    patient_count = await db.execute(select(func.count(Patient.id)))
    analysis_count = await db.execute(select(func.count(Analysis.id)))
    user_count = await db.execute(select(func.count(User.id)))
    report_count = await db.execute(select(func.count(Report.id)))
    validated = await db.execute(select(func.count(Analysis.id)).where(Analysis.status == "validated"))
    return {
        "patients": patient_count.scalar(),
        "analyses": analysis_count.scalar(),
        "users": user_count.scalar(),
        "reports": report_count.scalar(),
        "validated_analyses": validated.scalar(),
    }


@router.delete("/audit/purge")
async def purge_audit_logs(db: AsyncSession = Depends(get_db)):
    await db.execute(AuditLog.__table__.delete())
    await db.flush()
    return {"status": "purged"}


@router.get("/audit")
async def admin_audit(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/users/activity")
async def user_activity(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User.id, User.first_name, User.last_name, User.last_login).where(User.is_active == True)  # noqa: E712
    )
    users = result.all()
    return [
        {"id": u.id, "name": f"{u.first_name} {u.last_name}", "last_login": u.last_login}
        for u in users
    ]


@router.get("/performance")
async def admin_performance():
    return {"status": "metrics_collection_disabled_for_mvp"}
