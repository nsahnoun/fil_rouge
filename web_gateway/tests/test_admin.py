import pytest


class TestAdminStats:
    async def test_stats(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "patients" in data
        assert "analyses" in data
        assert "users" in data
        assert "reports" in data

    async def test_stats_forbidden(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/api/admin/stats", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 403


class TestAdminAudit:
    async def test_audit_logs_empty(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/admin/audit", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_audit_logs_with_data(self, client, admin_user, admin_token, session):
        from web_gateway.models import AuditLog
        session.add(AuditLog(user_id=admin_user.id, action="login", resource_type="auth"))
        await session.flush()
        await session.commit()
        resp = await client.get("/api/admin/audit", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["action"] == "login"

    async def test_audit_logs_limit(self, client, admin_user, admin_token, session):
        from web_gateway.models import AuditLog
        for i in range(5):
            session.add(AuditLog(user_id=admin_user.id, action=f"action_{i}", resource_type="test"))
        await session.flush()
        await session.commit()
        resp = await client.get("/api/admin/audit?limit=3", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestAdminUserActivity:
    async def test_user_activity(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.get("/api/admin/users/activity", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 2


class TestAdminPerformance:
    async def test_performance(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/admin/performance", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "metrics_collection_disabled_for_mvp"
