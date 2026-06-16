import os
from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..core.dependencies import get_current_user, require_role
from ..core.exceptions import NotFoundException
from ..models import Patient, Radio, User
from ..services.ceph_client import CephClient

router = APIRouter(dependencies=[Depends(get_current_user)])
ceph = CephClient()


@router.post("/upload")
async def upload_radio(
    patient_id: int,
    acquisition_date: str | None = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("patients", "write")),
):
    patient = await db.execute(select(Patient).where(Patient.id == patient_id))
    if not patient.scalar_one_or_none():
        raise NotFoundException("Patient introuvable")

    upload_dir = settings.upload_path / str(patient_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    radio = Radio(
        patient_id=patient_id,
        uploaded_by=current_user.id,
        filename=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=file.content_type or "image/png",
        acquisition_date=date.fromisoformat(acquisition_date) if acquisition_date else date.today(),
    )
    db.add(radio)
    await db.flush()

    prediction = await ceph.predict(file_path)
    if prediction:
        radio.image_width = prediction.get("image_width")
        radio.image_height = prediction.get("image_height")
        await db.flush()

    return {"id": radio.id, "filename": radio.filename, "prediction": prediction is not None}


@router.get("/by-patient/{patient_id}")
async def list_patient_radios(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Radio).where(Radio.patient_id == patient_id).order_by(Radio.created_at.desc())
    )
    radios = result.scalars().all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "mime_type": r.mime_type,
            "image_width": r.image_width,
            "image_height": r.image_height,
            "pixel_spacing": r.pixel_spacing,
            "acquisition_date": str(r.acquisition_date) if r.acquisition_date else None,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in radios
    ]


@router.get("/{radio_id}")
async def get_radio(radio_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Radio).where(Radio.id == radio_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Radio introuvable")
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "filename": r.filename,
        "file_path": r.file_path,
        "image_width": r.image_width,
        "image_height": r.image_height,
        "pixel_spacing": r.pixel_spacing,
        "acquisition_date": r.acquisition_date,
        "created_at": r.created_at,
    }


@router.get("/{radio_id}/image")
async def get_radio_image(radio_id: int, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import FileResponse

    result = await db.execute(select(Radio).where(Radio.id == radio_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Radio introuvable")
    if not os.path.exists(r.file_path):
        raise NotFoundException("Fichier image introuvable")
    return FileResponse(r.file_path, media_type=r.mime_type or "image/png")


@router.delete("/{radio_id}")
async def delete_radio(radio_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("patients", "delete_own"))):
    result = await db.execute(select(Radio).where(Radio.id == radio_id))
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundException("Radio introuvable")
    await db.delete(r)
    await db.flush()
    return {"status": "deleted"}
