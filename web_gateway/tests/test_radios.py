import pytest


class TestRadios:
    async def test_get_radio(self, client, ortho_user, ortho_token, radio, session):
        resp = await client.get(f"/api/radios/{radio.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "ceph.png"
        assert data["patient_id"] == radio.patient_id

    async def test_get_radio_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.get("/api/radios/9999", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404

    async def test_get_radio_image_not_found(self, client, ortho_user, ortho_token, radio, session):
        resp = await client.get(f"/api/radios/{radio.id}/image", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404

    async def test_delete_radio(self, client, ortho_user, ortho_token, radio, session):
        resp = await client.delete(f"/api/radios/{radio.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_delete_radio_not_found(self, client, ortho_user, ortho_token, session):
        resp = await client.delete("/api/radios/9999", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 404

    async def test_upload_radio_patient_not_found(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/radios/upload?patient_id=9999", files={
            "file": ("test.png", b"fake-image-data", "image/png"),
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_upload_radio_as_intern_forbidden(self, client, intern_user, intern_token, patient, session):
        resp = await client.post(f"/api/radios/upload?patient_id={patient.id}", files={
            "file": ("test.png", b"fake-image-data", "image/png"),
        }, headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403

    async def test_list_patient_radios(self, client, ortho_user, ortho_token, patient, radio, session):
        resp = await client.get(f"/api/radios/by-patient/{patient.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == radio.id
        assert data[0]["filename"] == "ceph.png"

    async def test_list_patient_radios_empty(self, client, ortho_user, ortho_token, patient, session):
        resp = await client.get(f"/api/radios/by-patient/{patient.id}", headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 200
        assert resp.json() == []
