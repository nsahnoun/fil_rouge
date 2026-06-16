import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.dependencies import get_current_user, require_role
from ..core.exceptions import NotFoundException
from ..models import Analysis, AnalysisComparison, Patient, Radio, ReviewRequest, User
from ..services.ceph_client import CephClient

router = APIRouter(dependencies=[Depends(get_current_user)])

# ── Static routes first (before /{analysis_id}) ────────────────────
@router.get("/methods")
async def list_methods():
    return {
        "methods": [
            "Ricketts", "Steiner", "Downs", "Tweed", "McNamara",
            "Bjork-Jarabak", "Wits", "Rakosi", "Segner-Hasund",
            "Eastman", "ABO", "Quick",
        ]
    }


@router.get("/compare")
async def compare_analyses(
    analysis_1_id: int,
    analysis_2_id: int,
    db: AsyncSession = Depends(get_db),
):
    a1 = await db.execute(select(Analysis).where(Analysis.id == analysis_1_id))
    a2 = await db.execute(select(Analysis).where(Analysis.id == analysis_2_id))
    a1_obj = a1.scalar_one_or_none()
    a2_obj = a2.scalar_one_or_none()
    if not a1_obj or not a2_obj:
        raise NotFoundException("Analyse introuvable")
    return {
        "analysis_1": {
            "id": a1_obj.id,
            "landmarks": json.loads(a1_obj.landmarks) if a1_obj.landmarks else [],
            "measurements": json.loads(a1_obj.measurements) if a1_obj.measurements else {},
            "created_at": a1_obj.created_at,
        },
        "analysis_2": {
            "id": a2_obj.id,
            "landmarks": json.loads(a2_obj.landmarks) if a2_obj.landmarks else [],
            "measurements": json.loads(a2_obj.measurements) if a2_obj.measurements else {},
            "created_at": a2_obj.created_at,
        },
    }


@router.get("/by-patient/{patient_id}")
async def list_patient_analyses(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Analysis).join(Radio).where(Radio.patient_id == patient_id).order_by(Analysis.created_at.desc())
    )
    analyses = result.scalars().all()
    return [
        {
            "id": a.id,
            "radio_id": a.radio_id,
            "status": a.status,
            "version": a.version,
            "inference_ms": a.inference_ms,
            "created_at": a.created_at,
            "validated_at": a.validated_at,
        }
        for a in analyses
    ]


@router.get("/evolution/{patient_id}")
async def patient_evolution(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AnalysisComparison).where(AnalysisComparison.patient_id == patient_id).order_by(AnalysisComparison.created_at.desc())
    )
    comparisons = result.scalars().all()
    return [
        {
            "id": c.id,
            "analysis_1_id": c.analysis_1_id,
            "analysis_2_id": c.analysis_2_id,
            "comparison_data": json.loads(c.comparison_data) if c.comparison_data else {},
            "created_at": c.created_at,
        }
        for c in comparisons
    ]


# ── Parameterized routes ──────────────────────────────────────────
@router.get("/{analysis_id}")
async def get_analysis(analysis_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .options(selectinload(Analysis.radio))
    )
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    return {
        "id": a.id,
        "radio_id": a.radio_id,
        "patient_id": a.radio.patient_id,
        "performed_by": a.performed_by,
        "validated_by": a.validated_by,
        "status": a.status,
        "landmarks": json.loads(a.landmarks) if a.landmarks else [],
        "measurements": json.loads(a.measurements) if a.measurements else {},
        "inference_ms": a.inference_ms,
        "tta_passes": a.tta_passes,
        "version": a.version,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


class UpdateLandmarksRequest(BaseModel):
    landmarks: list


@router.post("/{analysis_id}/landmarks")
async def update_landmarks(
    analysis_id: int,
    req: UpdateLandmarksRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    a.landmarks = json.dumps(req.landmarks)
    await db.flush()
    return {"status": "landmarks_updated"}


@router.post("/{analysis_id}/validate")
async def validate_analysis(
    analysis_id: int,
    comment: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("analyses", "validate")),
):
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    a.status = "validated"
    a.validated_by = current_user.id
    a.validation_comment = comment
    from datetime import datetime, timezone
    a.validated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "validated", "analysis_id": analysis_id}


@router.post("/{analysis_id}/request-review")
async def request_review(
    analysis_id: int,
    assigned_to: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    a.status = "pending_review"
    review = ReviewRequest(
        analysis_id=analysis_id,
        requested_by=current_user.id,
        assigned_to=assigned_to,
    )
    db.add(review)
    await db.flush()
    return {"status": "review_requested", "review_id": review.id}


@router.post("/{analysis_id}/review")
async def submit_review(
    analysis_id: int,
    approved: bool,
    reviewer_notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("analyses", "review")),
):
    result = await db.execute(
        select(ReviewRequest).where(
            ReviewRequest.analysis_id == analysis_id,
            ReviewRequest.assigned_to == current_user.id,
            ReviewRequest.status == "pending",
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise NotFoundException("Demande de révision introuvable")
    review.status = "completed" if approved else "rejected"
    review.reviewer_notes = reviewer_notes
    from datetime import datetime, timezone
    review.completed_at = datetime.now(timezone.utc)

    analysis = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    a = analysis.scalar_one_or_none()
    if a and approved:
        a.status = "validated"
        a.validated_by = current_user.id
        a.validated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "review_submitted", "approved": approved}


@router.delete("/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("analyses", "delete_own")),
):
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    await db.delete(a)
    await db.flush()
    return {"status": "deleted"}


@router.post("/{analysis_id}/predict")
async def predict_landmarks(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("analyses", "create")),
):
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id).options(selectinload(Analysis.radio))
    )
    a = result.scalar_one_or_none()
    if not a:
        raise NotFoundException("Analyse introuvable")
    radio = a.radio
    from pathlib import Path
    if not Path(radio.file_path).exists():
        raise NotFoundException("Fichier radio introuvable")
    ceph = CephClient()
    prediction = await ceph.predict(radio.file_path)
    if not prediction:
        raise HTTPException(502, "Échec de la détection automatique")
    landmarks = prediction.get("landmarks", [])
    a.landmarks = json.dumps(landmarks)
    a.inference_ms = prediction.get("inference_ms")
    await db.flush()
    return {"status": "predicted", "landmarks": landmarks, "inference_ms": prediction.get("inference_ms")}


class CreateAnalysisRequest(BaseModel):
    radio_id: int


@router.post("/create")
async def create_analysis(
    req: CreateAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("analyses", "create")),
):
    radio = await db.execute(select(Radio).where(Radio.id == req.radio_id))
    if not radio.scalar_one_or_none():
        raise NotFoundException("Radio introuvable")
    a = Analysis(
        radio_id=req.radio_id,
        performed_by=current_user.id,
        landmarks=json.dumps([]),
        measurements=json.dumps({}),
        status="draft",
    )
    db.add(a)
    await db.flush()
    return {"id": a.id, "status": "created"}
