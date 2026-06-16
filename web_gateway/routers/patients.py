from datetime import date

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.dependencies import get_current_user, require_role
from ..core.exceptions import NotFoundException
from ..models import ClinicalNote, Patient, PatientDocument, User

router = APIRouter(dependencies=[Depends(get_current_user)])


class CreatePatientRequest(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    gender: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    medical_id: str | None = None
    referring_doctor: str | None = None
    medical_history: str | None = None
    allergies: str | None = None
    medications: str | None = None
    insurance_info: str | None = None
    assigned_to: int | None = None


@router.get("")
async def list_patients(
    search: str | None = None,
    assigned_to: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Patient).options(selectinload(Patient.orthodontist))
    if current_user.role.name == "intern":
        query = query.where(Patient.assigned_to == current_user.id)
    if search:
        query = query.where(
            Patient.first_name.ilike(f"%{search}%") | Patient.last_name.ilike(f"%{search}%")
        )
    if assigned_to:
        query = query.where(Patient.assigned_to == assigned_to)
    query = query.order_by(Patient.created_at.desc())
    result = await db.execute(query)
    patients = result.scalars().all()
    return [
        {
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "birth_date": p.birth_date,
            "gender": p.gender,
            "phone": p.phone,
            "email": p.email,
            "medical_id": p.medical_id,
            "assigned_to_name": p.orthodontist.first_name + " " + p.orthodontist.last_name if p.orthodontist else None,
            "consent_signed": p.consent_signed,
            "created_at": p.created_at,
        }
        for p in patients
    ]


@router.post("")
async def create_patient(
    req: CreatePatientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("patients", "create")),
):
    patient = Patient(
        first_name=req.first_name,
        last_name=req.last_name,
        birth_date=req.birth_date,
        gender=req.gender,
        email=req.email,
        phone=req.phone,
        address=req.address,
        medical_id=req.medical_id,
        referring_doctor=req.referring_doctor,
        medical_history=req.medical_history,
        allergies=req.allergies,
        medications=req.medications,
        insurance_info=req.insurance_info,
        assigned_to=req.assigned_to or current_user.id,
        created_by=current_user.id,
    )
    db.add(patient)
    await db.flush()
    return {"id": patient.id, "first_name": patient.first_name, "last_name": patient.last_name}


@router.get("/{patient_id}")
async def get_patient(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Patient)
        .where(Patient.id == patient_id)
        .options(selectinload(Patient.orthodontist), selectinload(Patient.creator))
    )
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundException("Patient introuvable")
    return {
        "id": p.id,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "birth_date": p.birth_date,
        "gender": p.gender,
        "email": p.email,
        "phone": p.phone,
        "address": p.address,
        "emergency_contact": p.emergency_contact,
        "emergency_phone": p.emergency_phone,
        "medical_id": p.medical_id,
        "referring_doctor": p.referring_doctor,
        "medical_history": p.medical_history,
        "allergies": p.allergies,
        "medications": p.medications,
        "insurance_info": p.insurance_info,
        "consent_signed": p.consent_signed,
        "consent_signed_at": p.consent_signed_at,
        "assigned_to": p.assigned_to,
        "assigned_to_name": p.orthodontist.first_name + " " + p.orthodontist.last_name if p.orthodontist else None,
        "created_by_name": p.creator.first_name + " " + p.creator.last_name if p.creator else None,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.put("/{patient_id}")
async def update_patient(
    patient_id: int,
    req: CreatePatientRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("patients", "update")),
):
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundException("Patient introuvable")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.flush()
    return {"status": "updated"}


@router.delete("/{patient_id}")
async def delete_patient(patient_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("patients", "delete_own"))):
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundException("Patient introuvable")
    await db.delete(p)
    await db.flush()
    return {"status": "deleted"}


# ── Timeline ──────────────────────────────────────────────────────
@router.get("/{patient_id}/timeline")
async def patient_timeline(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClinicalNote).where(ClinicalNote.patient_id == patient_id).order_by(ClinicalNote.created_at.desc())
    )
    notes = result.scalars().all()
    return [
        {"type": "note", "id": n.id, "note_type": n.note_type, "content": n.content[:200], "created_at": n.created_at}
        for n in notes
    ]


# ── Documents ─────────────────────────────────────────────────────
@router.get("/{patient_id}/documents")
async def list_documents(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PatientDocument).where(PatientDocument.patient_id == patient_id).order_by(PatientDocument.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [{"id": d.id, "filename": d.filename, "file_type": d.file_type, "description": d.description, "uploaded_at": d.uploaded_at} for d in docs]


@router.post("/{patient_id}/documents")
async def upload_document(
    patient_id: int,
    file: UploadFile,
    file_type: str | None = None,
    description: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = PatientDocument(
        patient_id=patient_id,
        uploaded_by=current_user.id,
        filename=file.filename,
        file_path=f"uploads/{patient_id}/{file.filename}",
        file_type=file_type,
        description=description,
    )
    db.add(doc)
    await db.flush()
    return {"id": doc.id, "filename": doc.filename}


# ── Notes cliniques ───────────────────────────────────────────────
@router.get("/{patient_id}/notes")
async def list_notes(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClinicalNote).where(ClinicalNote.patient_id == patient_id).order_by(ClinicalNote.created_at.desc())
    )
    notes = result.scalars().all()
    return [
        {"id": n.id, "note_type": n.note_type, "content": n.content, "is_confidential": n.is_confidential, "created_at": n.created_at}
        for n in notes
    ]


class CreateNoteRequest(BaseModel):
    note_type: str
    content: str
    is_confidential: bool = False


@router.post("/{patient_id}/notes")
async def create_note(
    patient_id: int,
    req: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = ClinicalNote(
        patient_id=patient_id,
        created_by=current_user.id,
        note_type=req.note_type,
        content=req.content,
        is_confidential=req.is_confidential,
    )
    db.add(note)
    await db.flush()
    return {"id": note.id, "note_type": note.note_type, "created_at": note.created_at}
