import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from web_gateway.models import (
    Analysis, AnalysisComparison, AuditLog, ClinicSetting, ClinicalNote,
    ConsentLog, Notification, Patient, PatientDocument, Radio, Report,
    ReportTemplate, ReviewRequest, Role, Task, User, UserPreference, UserSession,
)


class TestModelCreation:
    async def test_create_all_models(self, session, roles, admin_user, ortho_user, patient, radio, analysis):
        assert roles["admin"].id is not None
        assert admin_user.id is not None
        assert ortho_user.id is not None
        assert patient.id is not None
        assert radio.id is not None
        assert analysis.id is not None

    async def test_patient_document(self, session, patient, ortho_user):
        doc = PatientDocument(patient_id=patient.id, uploaded_by=ortho_user.id, filename="test.pdf", file_path="/tmp/test.pdf")
        session.add(doc)
        await session.flush()
        assert doc.id is not None

    async def test_clinical_note(self, session, patient, ortho_user):
        note = ClinicalNote(patient_id=patient.id, created_by=ortho_user.id, note_type="consultation", content="Test note")
        session.add(note)
        await session.flush()
        assert note.id is not None

    async def test_analysis_comparison(self, session, patient, analysis, radio):
        from web_gateway.models import Analysis
        a2 = Analysis(radio_id=radio.id, performed_by=analysis.performed_by, landmarks="[]")
        session.add(a2)
        await session.flush()
        comp = AnalysisComparison(patient_id=patient.id, analysis_1_id=analysis.id, analysis_2_id=a2.id, comparison_data=json.dumps({"diff": 1.0}))
        session.add(comp)
        await session.flush()
        assert comp.id is not None

    async def test_report_template(self, session, admin_user):
        tmpl = ReportTemplate(name="Test Template", template_html="<html></html>", created_by=admin_user.id)
        session.add(tmpl)
        await session.flush()
        assert tmpl.id is not None

    async def test_report(self, session, patient, analysis, ortho_user, admin_user):
        tmpl = ReportTemplate(name="Tmpl", template_html="<html></html>", created_by=admin_user.id)
        session.add(tmpl)
        await session.flush()
        report = Report(patient_id=patient.id, analysis_id=analysis.id, generated_by=ortho_user.id, report_type="clinical", template_id=tmpl.id)
        session.add(report)
        await session.flush()
        assert report.id is not None

    async def test_review_request(self, session, analysis, ortho_user, admin_user):
        rr = ReviewRequest(analysis_id=analysis.id, requested_by=ortho_user.id, assigned_to=admin_user.id)
        session.add(rr)
        await session.flush()
        assert rr.id is not None

    async def test_task(self, session, patient, ortho_user):
        from datetime import date
        task = Task(patient_id=patient.id, assigned_to=ortho_user.id, created_by=ortho_user.id, title="Test task", due_date=date.today())
        session.add(task)
        await session.flush()
        assert task.id is not None

    async def test_audit_log(self, session, admin_user):
        log = AuditLog(user_id=admin_user.id, action="create", resource_type="patient", resource_id=1)
        session.add(log)
        await session.flush()
        assert log.id is not None

    async def test_consent_log(self, session, patient, admin_user):
        cl = ConsentLog(patient_id=patient.id, consent_type="treatment", version="1.0", signed_by=admin_user.id)
        session.add(cl)
        await session.flush()
        assert cl.id is not None

    async def test_clinic_setting(self, session, admin_user):
        cs = ClinicSetting(setting_key="clinic_name", setting_value="Test Clinic", updated_by=admin_user.id)
        session.add(cs)
        await session.flush()
        assert cs.id is not None

    async def test_user_preference(self, session, admin_user):
        pref = UserPreference(user_id=admin_user.id, pref_key="theme", pref_value="dark")
        session.add(pref)
        await session.flush()
        assert pref.id is not None

    async def test_notification(self, session, admin_user):
        notif = Notification(user_id=admin_user.id, type="info", title="Welcome", message="Hello!")
        session.add(notif)
        await session.flush()
        assert notif.id is not None

    async def test_user_session(self, session, admin_user):
        us = UserSession(user_id=admin_user.id, session_token="tok123", expires_at=datetime.now(timezone.utc))
        session.add(us)
        await session.flush()
        assert us.id is not None


class TestModelRelationships:
    async def test_patient_has_radios(self, session, patient, radio):
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Patient).where(Patient.id == patient.id).options(selectinload(Patient.radios))
        )
        p = result.scalar_one()
        assert len(p.radios) == 1
        assert p.radios[0].id == radio.id

    async def test_user_has_role(self, session, admin_user):
        result = await session.execute(select(User).where(User.id == admin_user.id))
        u = result.scalar_one()
        assert u.role.name == "admin"

    async def test_analysis_belongs_to_radio(self, session, analysis, radio):
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Analysis).where(Analysis.id == analysis.id).options(selectinload(Analysis.radio))
        )
        a = result.scalar_one()
        assert a.radio.id == radio.id
