import pytest


class TestListUsers:
    async def test_list_users(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        emails = [u["email"] for u in data]
        assert "admin@test.com" in emails
        assert "ortho@test.com" in emails

    async def test_list_users_forbidden(self, client, intern_user, intern_token, session):
        resp = await client.get("/api/users", headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403


class TestCreateUser:
    async def test_create_user(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/users", json={
            "email": "newdoc@test.com",
            "password": "docpass",
            "first_name": "New",
            "last_name": "Doctor",
            "role_name": "orthodontist",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newdoc@test.com"
        assert data["role"] == "orthodontist"

    async def test_create_user_duplicate_email(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/users", json={
            "email": "admin@test.com",
            "password": "pass",
            "first_name": "Dup",
            "last_name": "User",
            "role_name": "intern",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 409

    async def test_create_user_invalid_role(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/users", json={
            "email": "badrole@test.com",
            "password": "pass",
            "first_name": "Bad",
            "last_name": "Role",
            "role_name": "nonexistent",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_create_user_forbidden(self, client, ortho_user, ortho_token, session):
        resp = await client.post("/api/users", json={
            "email": "test@test.com",
            "password": "pass",
            "first_name": "Test",
            "last_name": "User",
            "role_name": "intern",
        }, headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 403


class TestGetUser:
    async def test_get_user(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.get(f"/api/users/{ortho_user.id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "ortho@test.com"

    async def test_get_user_not_found(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/users/9999", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_get_user_by_self(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.get(f"/api/users/{ortho_user.id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200


class TestUpdateUser:
    async def test_update_user(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.put(f"/api/users/{ortho_user.id}?first_name=Updated&is_active=true",
                                headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    async def test_update_user_not_found(self, client, admin_user, admin_token, session):
        resp = await client.put("/api/users/9999?first_name=X",
                                headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_update_user_role(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.put(f"/api/users/{ortho_user.id}?role_name=assistant",
                                headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

    async def test_update_user_invalid_role(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.put(f"/api/users/{ortho_user.id}?role_name=nonexistent",
                                headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_update_user_forbidden(self, client, intern_user, intern_token, ortho_user, session):
        resp = await client.put(f"/api/users/{ortho_user.id}?first_name=X",
                                headers={"Authorization": f"Bearer {intern_token}"})
        assert resp.status_code == 403


class TestDeactivateUser:
    async def test_deactivate_user(self, client, admin_user, admin_token, ortho_user, session):
        resp = await client.delete(f"/api/users/{ortho_user.id}",
                                   headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"
        assert ortho_user.is_active is False

    async def test_deactivate_user_not_found(self, client, admin_user, admin_token, session):
        resp = await client.delete("/api/users/9999",
                                   headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

    async def test_deactivate_user_forbidden(self, client, ortho_user, ortho_token, admin_user, session):
        resp = await client.delete(f"/api/users/{admin_user.id}",
                                   headers={"Authorization": f"Bearer {ortho_token}"})
        assert resp.status_code == 403
