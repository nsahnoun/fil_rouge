import pytest


class TestCephClient:
    async def test_health_no_server(self):
        from web_gateway.services.ceph_client import ceph_client_override_url, CephClient
        ceph_client_override_url("http://localhost:19999")
        client = CephClient()
        result = await client.health()
        assert result is None

    async def test_predict_no_server(self):
        from web_gateway.services.ceph_client import ceph_client_override_url, CephClient
        import tempfile, os
        ceph_client_override_url("http://localhost:19999")
        client = CephClient()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-data")
            tmp = f.name
        try:
            result = await client.predict(tmp)
            assert result is None
        finally:
            os.unlink(tmp)


class TestAuditService:
    async def test_log_audit(self):
        from web_gateway.services.audit_service import log_audit
        from web_gateway.core.database import async_session
        from web_gateway.models import AuditLog
        from sqlalchemy import select

        result = await log_audit(
            user_id=1,
            action="test_action",
            resource_type="test",
            resource_id=42,
            old_values={"key": "old"},
            new_values={"key": "new"},
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
        assert result is None  # function returns None on success

    async def test_log_audit_no_user(self):
        from web_gateway.services.audit_service import log_audit
        result = await log_audit(
            user_id=None,
            action="system",
            resource_type="test",
        )
        assert result is None

    class TestReportService:
        async def test_generate_pdf_missing_data(self):
            from web_gateway.services.report_service import generate_pdf
            result = await generate_pdf(
                report_id=1,
                patient={"first_name": "Test"},
                analysis={"id": 1},
                measurements={},
                orthodontist={"first_name": "Dr"},
            )
            assert result is not None
            assert "report_1.pdf" in result
