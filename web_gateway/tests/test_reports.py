import pytest


class TestReportTemplates:
    async def test_list_templates_empty(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/api/reports/templates", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_template(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/reports/templates", json={
            "name": "Standard",
            "description": "Template standard",
            "template_html": "<html><body>{{content}}</body></html>",
            "is_default": True,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Standard"

    async def test_create_template_forbidden(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/reports/templates", json={
            "name": "Test",
            "template_html": "<html></html>",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 403

    async def test_list_templates_after_create(self, client, admin_user, admin_token, session):
        from web_gateway.models import ReportTemplate
        session.add(ReportTemplate(name="Default", template_html="<html></html>", created_by=admin_user.id))
        await session.flush()
        await session.commit()
        resp = await client.get("/api/reports/templates", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGenerateReport:
    async def test_generate_report(self, client, ortho_user, ortho_token, patient, analysis, session):
        resp = await client.post("/api/reports/generate", json={
            "patient_id": patient.id,
            "analysis_id": analysis.id,
            "report_type": "clinical",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "generated"

    async def test_generate_report_with_template(self, client, admin_user, admin_token, patient, analysis, session):
        from web_gateway.models import ReportTemplate
        tmpl = ReportTemplate(name="Custom", template_html="<html></html>", created_by=admin_user.id)
        session.add(tmpl)
        await session.flush()
        await session.commit()
        resp = await client.post("/api/reports/generate", json={
            "patient_id": patient.id,
            "analysis_id": analysis.id,
            "template_id": tmpl.id,
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "generated"

    async def test_generate_report_with_invalid_template(self, client, ortho_user, ortho_token, patient, analysis, session):
        resp = await client.post("/api/reports/generate", json={
            "patient_id": patient.id,
            "analysis_id": analysis.id,
            "template_id": 9999,
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestGetReport:
    async def test_get_report(self, client, ortho_user, ortho_token, patient, analysis, session):
        from web_gateway.models import Report
        r = Report(patient_id=patient.id, analysis_id=analysis.id, generated_by=ortho_user.id, report_type="clinical")
        session.add(r)
        await session.flush()
        await session.commit()
        resp = await client.get(f"/api/reports/{r.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["report_type"] == "clinical"


class TestSignReport:
    async def test_sign_report(self, client, ortho_user, ortho_token, patient, analysis, session):
        from web_gateway.models import Report
        r = Report(patient_id=patient.id, analysis_id=analysis.id, generated_by=ortho_user.id, report_type="clinical")
        session.add(r)
        await session.flush()
        await session.commit()
        resp = await client.post(f"/api/reports/{r.id}/sign", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "signed"

    async def test_sign_report_forbidden(self, client, intern_user, intern_token, patient, analysis, session):
        from web_gateway.models import Report
        r = Report(patient_id=patient.id, analysis_id=analysis.id, generated_by=intern_user.id, report_type="clinical")
        session.add(r)
        await session.flush()
        await session.commit()
        resp = await client.post(f"/api/reports/{r.id}/sign", headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403
