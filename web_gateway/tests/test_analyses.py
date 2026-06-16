import json
import pytest


class TestGetAnalysis:
    async def test_get_analysis(self, client, ortho_user, ortho_token, analysis, session):
        resp = await client.get(f"/api/analyses/{analysis.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert len(data["landmarks"]) == 1

    async def test_get_analysis_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/api/analyses/9999", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestUpdateLandmarks:
    async def test_update_landmarks(self, client, ortho_user, ortho_token, analysis, session):
        resp = await client.post(f"/api/analyses/{analysis.id}/landmarks", json={
            "landmarks": [{"name": "N", "x": 150, "y": 250}, {"name": "A", "x": 200, "y": 300}],
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "landmarks_updated"

    async def test_update_landmarks_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/analyses/9999/landmarks", json={"landmarks": []},
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestValidateAnalysis:
    async def test_validate_analysis(self, client, ortho_user, ortho_token, analysis, session):
        resp = await client.post(f"/api/analyses/{analysis.id}/validate?comment=OK",
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "validated"

    async def test_validate_analysis_as_intern_forbidden(self, client, intern_user, intern_token, analysis, session):
        resp = await client.post(f"/api/analyses/{analysis.id}/validate",
                                 headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403


class TestReviewRequest:
    async def test_request_review(self, client, ortho_user, ortho_token, analysis, admin_user, session):
        resp = await client.post(f"/api/analyses/{analysis.id}/request-review?assigned_to={admin_user.id}",
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "review_requested"

    async def test_request_review_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/analyses/9999/request-review?assigned_to=1",
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404

    async def test_submit_review_complete(self, client, ortho_user, ortho_token, analysis, admin_user, admin_token, session):
        from web_gateway.models import ReviewRequest
        r = ReviewRequest(analysis_id=analysis.id, requested_by=ortho_user.id, assigned_to=admin_user.id, status="pending")
        session.add(r)
        await session.flush()
        await session.commit()
        resp = await client.post(f"/api/analyses/{analysis.id}/review?approved=true&reviewer_notes=Good",
                                 headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["approved"] is True

    async def test_submit_review_reject(self, client, ortho_user, ortho_token, analysis, admin_user, admin_token, session):
        from web_gateway.models import ReviewRequest
        r = ReviewRequest(analysis_id=analysis.id, requested_by=ortho_user.id, assigned_to=admin_user.id, status="pending")
        session.add(r)
        await session.flush()
        await session.commit()
        resp = await client.post(f"/api/analyses/{analysis.id}/review?approved=false&reviewer_notes=Needs+work",
                                 headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["approved"] is False

    async def test_submit_review_no_pending(self, client, admin_user, admin_token, analysis, session):
        resp = await client.post(f"/api/analyses/{analysis.id}/review?approved=true",
                                 headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404


class TestCompareAnalyses:
    async def test_compare(self, client, ortho_user, ortho_token, analysis, radio, session):
        from web_gateway.models import Analysis
        import json
        a2 = Analysis(radio_id=radio.id, performed_by=ortho_user.id,
                      landmarks=json.dumps([{"name": "N", "x": 110, "y": 210}]),
                      measurements=json.dumps({"SNA": 83.0}))
        session.add(a2)
        await session.flush()
        await session.commit()
        resp = await client.get(f"/api/analyses/compare?analysis_1_id={analysis.id}&analysis_2_id={a2.id}",
                                headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_1"]["id"] == analysis.id
        assert data["analysis_2"]["id"] == a2.id

    async def test_compare_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/api/analyses/compare?analysis_1_id=1&analysis_2_id=9999",
                                headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestListMethods:
    async def test_list_methods(self, client, ortho_token):
        resp = await client.get("/api/analyses/methods", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "Ricketts" in data["methods"]
        assert len(data["methods"]) == 12


class TestPatientAnalyses:
    async def test_list_by_patient(self, client, ortho_user, ortho_token, analysis, patient, session):
        resp = await client.get(f"/api/analyses/by-patient/{patient.id}",
                                headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == analysis.id


class TestEvolution:
    async def test_evolution_empty(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.get(f"/api/analyses/evolution/{patient.id}",
                                headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateAnalysis:
    async def test_create_analysis(self, client, ortho_user, ortho_token, radio, session):
        resp = await client.post("/api/analyses/create", json={"radio_id": radio.id},
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["id"] > 0

    async def test_create_analysis_radio_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/analyses/create", json={"radio_id": 9999},
                                 headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404

    async def test_create_analysis_as_intern_forbidden(self, client, intern_user, intern_token, radio, session):
        resp = await client.post("/api/analyses/create", json={"radio_id": radio.id},
                                 headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403


class TestDeleteAnalysis:
    async def test_delete_analysis_as_admin(self, client, admin_user, admin_token, analysis, session):
        resp = await client.delete(f"/api/analyses/{analysis.id}",
                                   headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_delete_analysis_as_orthodontist(self, client, ortho_user, ortho_token, analysis, session):
        resp = await client.delete(f"/api/analyses/{analysis.id}",
                                   headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_delete_analysis_as_assistant_forbidden(self, client, assistant_user, assistant_token, analysis, session):
        resp = await client.delete(f"/api/analyses/{analysis.id}",
                                   headers={"Authorization": f"Bearer {assistant_token}"})
        assert resp.status_code == 403

    async def test_delete_analysis_as_intern_forbidden(self, client, intern_user, intern_token, analysis, session):
        resp = await client.delete(f"/api/analyses/{analysis.id}",
                                   headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403

    async def test_delete_analysis_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.delete("/api/analyses/9999",
                                   headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404
