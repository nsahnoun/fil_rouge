import pytest
from datetime import date


class TestListPatients:
    async def test_list_empty(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/patients", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_patients(self, client, admin_user, admin_token, patient, session):
        resp = await client.get("/api/patients", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["first_name"] == "Jean"

    async def test_list_search(self, client, admin_user, admin_token, patient, session):
        resp = await client.get("/api/patients?search=Dupont", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_list_search_no_match(self, client, admin_user, admin_token, patient, session):
        resp = await client.get("/api/patients?search=Inconnu", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_intern_sees_only_assigned(self, client, intern_user, intern_token, patient, session):
        resp = await client.get("/api/patients", headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestCreatePatient:
    async def test_create_as_orthodontist(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/patients", json={
            "first_name": "Marie",
            "last_name": "Curie",
            "birth_date": "1985-03-20",
            "gender": "F",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["first_name"] == "Marie"
        assert data["id"] is not None

    async def test_create_as_intern_forbidden(self, client, intern_user, intern_token, session):
        resp = await client.post("/api/patients", json={
            "first_name": "Test",
            "last_name": "User",
            "birth_date": "2000-01-01",
        }, headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403


class TestGetPatient:
    async def test_get_patient(self, client, admin_user, admin_token, patient, session):
        resp = await client.get(f"/api/patients/{patient.id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["first_name"] == "Jean"
        assert data["last_name"] == "Dupont"

    async def test_get_patient_not_found(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/patients/9999", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404


class TestUpdatePatient:
    async def test_update_patient(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.put(f"/api/patients/{patient.id}", json={
            "first_name": "Jean Updated",
            "last_name": "Dupont",
            "birth_date": "1990-05-15",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    async def test_update_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.put("/api/patients/9999", json={
            "first_name": "X",
            "last_name": "Y",
            "birth_date": "2000-01-01",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestDeletePatient:
    async def test_delete_patient(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.delete(f"/api/patients/{patient.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_delete_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.delete("/api/patients/9999", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404


class TestPatientNotes:
    async def test_list_notes_empty(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.get(f"/api/patients/{patient.id}/notes", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_note(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.post(f"/api/patients/{patient.id}/notes", json={
            "note_type": "consultation",
            "content": "Patient se présente bien.",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["note_type"] == "consultation"

    async def test_list_notes_after_create(self, client, ortho_user, ortho_token, patient, session):
        from web_gateway.models import ClinicalNote
        session.add(ClinicalNote(patient_id=patient.id, created_by=ortho_user.id, note_type="follow_up", content="Suivi"))
        await session.flush()
        await session.commit()
        resp = await client.get(f"/api/patients/{patient.id}/notes", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestPatientDocuments:
    async def test_list_docs_empty(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.get(f"/api/patients/{patient.id}/documents", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_upload_document(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.post(f"/api/patients/{patient.id}/documents?file_type=radio&description=test", files={
            "file": ("test.pdf", b"%PDF-1.4 content", "application/pdf"),
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.pdf"


class TestPatientTimeline:
    async def test_timeline_empty(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.get(f"/api/patients/{patient.id}/timeline", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_timeline_with_notes(self, client, ortho_user, ortho_token, patient, session):
        from web_gateway.models import ClinicalNote
        session.add(ClinicalNote(patient_id=patient.id, created_by=ortho_user.id, note_type="consultation", content="First visit"))
        await session.flush()
        await session.commit()
        resp = await client.get(f"/api/patients/{patient.id}/timeline", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["type"] == "note"
