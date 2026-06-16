from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


# ── 1. ROLES ───────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    permissions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    users = relationship("User", back_populates="role")


# ── 2. USERS ───────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    speciality = Column(String)
    license_number = Column(String)
    signature_image = Column(Text)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, onupdate=_utcnow)

    role = relationship("Role", back_populates="users")
    patients_created = relationship("Patient", back_populates="creator", foreign_keys="Patient.created_by")
    patients_assigned = relationship("Patient", back_populates="orthodontist", foreign_keys="Patient.assigned_to")
    sessions = relationship("UserSession", back_populates="user")
    preferences = relationship("UserPreference", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


# ── 3. USER SESSIONS ───────────────────────────────────────────────
class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String, unique=True, nullable=False)
    ip_address = Column(String)
    user_agent = Column(String)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="sessions")


# ── 4. PATIENTS ────────────────────────────────────────────────────
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    gender = Column(String, CheckConstraint("gender IN ('M','F','O')"))
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    emergency_contact = Column(String)
    emergency_phone = Column(String)
    medical_id = Column(String, unique=True)
    referring_doctor = Column(String)
    medical_history = Column(Text)
    allergies = Column(String)
    medications = Column(String)
    insurance_info = Column(String)
    consent_signed = Column(Boolean, default=False)
    consent_signed_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, onupdate=_utcnow)

    creator = relationship("User", back_populates="patients_created", foreign_keys=[created_by])
    orthodontist = relationship("User", back_populates="patients_assigned", foreign_keys=[assigned_to])
    documents = relationship("PatientDocument", back_populates="patient")
    notes = relationship("ClinicalNote", back_populates="patient")
    radios = relationship("Radio", back_populates="patient")
    comparisons = relationship("AnalysisComparison", back_populates="patient")
    reports = relationship("Report", back_populates="patient")
    tasks = relationship("Task", back_populates="patient")
    consent_logs = relationship("ConsentLog", back_populates="patient")


# ── 5. PATIENT DOCUMENTS ───────────────────────────────────────────
class PatientDocument(Base):
    __tablename__ = "patient_documents"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    description = Column(String)
    uploaded_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="documents")


# ── 6. CLINICAL NOTES ──────────────────────────────────────────────
class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    note_type = Column(String, CheckConstraint("note_type IN ('consultation','treatment_plan','follow_up','surgical')"))
    content = Column(Text)
    attachments = Column(Text)
    is_confidential = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="notes")


# ── 7. RADIOS ──────────────────────────────────────────────────────
class Radio(Base):
    __tablename__ = "radios"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    image_width = Column(Integer)
    image_height = Column(Integer)
    pixel_spacing = Column(Float)
    laterality = Column(String, default="L")
    acquisition_date = Column(Date, nullable=False)
    acquisition_device = Column(String)
    exposure_params = Column(String)
    is_dicom = Column(Boolean, default=False)
    dicom_tags = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="radios")
    analyses = relationship("Analysis", back_populates="radio")


# ── 8. ANALYSES ────────────────────────────────────────────────────
class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True)
    radio_id = Column(Integer, ForeignKey("radios.id"), nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"))
    validated_by = Column(Integer, ForeignKey("users.id"))
    analysis_type = Column(String, default="ceph")
    inference_ms = Column(Float)
    tta_passes = Column(Integer)
    landmarks = Column(Text, nullable=False)
    measurements = Column(Text)
    analysis_scores = Column(Text)
    status = Column(String, default="draft")
    validation_comment = Column(String)
    validated_at = Column(DateTime)
    version = Column(Integer, default=1)
    previous_version_id = Column(Integer, ForeignKey("analyses.id"))
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, onupdate=_utcnow)

    radio = relationship("Radio", back_populates="analyses")
    reports = relationship("Report", back_populates="analysis")
    review_requests = relationship("ReviewRequest", back_populates="analysis")


# ── 9. ANALYSIS COMPARISONS ────────────────────────────────────────
class AnalysisComparison(Base):
    __tablename__ = "analysis_comparisons"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    analysis_1_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    analysis_2_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    comparison_data = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="comparisons")


# ── 10. REPORT TEMPLATES ───────────────────────────────────────────
class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    template_html = Column(Text, nullable=False)
    template_css = Column(Text)
    is_default = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_utcnow)


# ── 11. REPORTS ────────────────────────────────────────────────────
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    analysis_id = Column(Integer, ForeignKey("analyses.id"))
    generated_by = Column(Integer, ForeignKey("users.id"))
    report_type = Column(String, nullable=False)
    template_id = Column(Integer, ForeignKey("report_templates.id"))
    content_html = Column(Text)
    file_path = Column(String)
    file_size = Column(Integer)
    recipient_email = Column(String)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    signed_by = Column(Integer, ForeignKey("users.id"))
    signed_at = Column(DateTime)
    digital_signature = Column(String)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="reports")
    analysis = relationship("Analysis", back_populates="reports")


# ── 12. REVIEW REQUESTS ────────────────────────────────────────────
class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")
    comments = Column(Text)
    reviewer_notes = Column(Text)
    requested_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime)

    analysis = relationship("Analysis", back_populates="review_requests")


# ── 13. TASKS ──────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    description = Column(String)
    due_date = Column(Date)
    priority = Column(String, default="medium")
    status = Column(String, default="pending")
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="tasks")


# ── 14. AUDIT LOGS ─────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(Integer)
    old_values = Column(Text)
    new_values = Column(Text)
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="audit_logs")


# ── 15. CONSENT LOGS ───────────────────────────────────────────────
class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    consent_type = Column(String, nullable=False)
    version = Column(String, nullable=False)
    is_signed = Column(Boolean, default=False)
    signed_by = Column(Integer, ForeignKey("users.id"))
    signed_at = Column(DateTime)
    ip_address = Column(String)
    document_hash = Column(String)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)

    patient = relationship("Patient", back_populates="consent_logs")


# ── 16. CLINIC SETTINGS ────────────────────────────────────────────
class ClinicSetting(Base):
    __tablename__ = "clinic_settings"

    id = Column(Integer, primary_key=True)
    setting_key = Column(String, unique=True, nullable=False)
    setting_value = Column(String)
    description = Column(String)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, onupdate=_utcnow)


# ── 17. USER PREFERENCES ───────────────────────────────────────────
class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pref_key = Column(String, nullable=False)
    pref_value = Column(String)
    __table_args__ = (UniqueConstraint("user_id", "pref_key"),)

    user = relationship("User", back_populates="preferences")


# ── 18. NOTIFICATIONS ──────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(String)
    link = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="notifications")
