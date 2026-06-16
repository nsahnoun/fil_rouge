import pytest


class TestPageRoutes:
    async def test_login_page(self, client, session):
        resp = await client.get("/login")
        assert resp.status_code == 200
        assert "CephAnalysis" in resp.text

    async def test_register_page(self, client, session):
        resp = await client.get("/auth/register")
        assert resp.status_code == 200
        assert "Créer un compte" in resp.text

    async def test_root_redirects(self, client, session):
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code == 307

    async def test_dashboard_redirects_when_unauthenticated(self, client, session):
        resp = await client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 307

    async def test_dashboard_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/dashboard", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Tableau de bord" in resp.text

    async def test_patients_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/patients", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Patients" in resp.text

    async def test_patient_new_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/patients/new", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Nouveau patient" in resp.text

    async def test_patient_detail_page(self, client, admin_user, admin_token, patient, session):
        resp = await client.get(f"/patients/{patient.id}", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert patient.first_name in resp.text

    async def test_patient_detail_404(self, client, admin_user, admin_token, session):
        resp = await client.get("/patients/9999", cookies={"access_token": admin_token})
        assert resp.status_code == 404

    async def test_analyses_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/analyses", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Analyses" in resp.text

    async def test_reports_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/reports", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Rapports" in resp.text

    async def test_admin_users_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/admin/users", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Utilisateurs" in resp.text

    async def test_admin_users_page_forbidden_for_non_admin(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/admin/users", cookies={"access_token": ortho_token}, follow_redirects=False)
        assert resp.status_code == 307

    async def test_admin_audit_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/admin/audit", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert "Audit" in resp.text

    async def test_admin_settings_page(self, client, admin_user, admin_token, session):
        resp = await client.get("/admin/settings", cookies={"access_token": admin_token})
        assert resp.status_code == 200

    async def test_logout_page(self, client, session):
        resp = await client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code == 307
