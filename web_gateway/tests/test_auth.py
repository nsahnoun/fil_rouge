import pytest


class TestAuthRegister:
    async def test_register_first_user_is_admin(self, client, roles, session):
        resp = await client.post("/api/auth/register", json={
            "email": "first@test.com",
            "password": "secret",
            "first_name": "First",
            "last_name": "Admin",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert "access_token" in data

    async def test_register_second_user_is_intern(self, client, admin_user, roles, session):
        resp = await client.post("/api/auth/register", json={
            "email": "second@test.com",
            "password": "secret",
            "first_name": "Second",
            "last_name": "User",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "intern"

    async def test_register_duplicate_email(self, client, admin_user, roles, session):
        resp = await client.post("/api/auth/register", json={
            "email": "admin@test.com",
            "password": "secret",
            "first_name": "Dup",
            "last_name": "User",
        })
        assert resp.status_code == 409


class TestAuthLogin:
    async def test_login_success(self, client, admin_user, session):
        resp = await client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "admin"
        assert data["name"] == "Admin User"

    async def test_login_wrong_password(self, client, admin_user, session):
        resp = await client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client, roles, session):
        from web_gateway.core.security import hash_password
        from web_gateway.models import User
        u = User(
            email="inactive@test.com",
            password_hash=hash_password("pass"),
            first_name="In",
            last_name="Active",
            role_id=roles["intern"].id,
            is_active=False,
        )
        session.add(u)
        await session.flush()
        await session.commit()
        resp = await client.post("/api/auth/login", json={
            "email": "inactive@test.com",
            "password": "pass",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client, session):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "pass",
        })
        assert resp.status_code == 401


class TestAuthMe:
    async def test_get_me_with_token(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["first_name"] == "Admin"

    async def test_get_me_with_cookie(self, client, admin_user, admin_token, session):
        resp = await client.get("/api/auth/me", cookies={"access_token": admin_token})
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@test.com"

    async def test_get_me_no_token(self, client, session):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client, session):
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401

    async def test_update_me(self, client, admin_user, admin_token, session):
        resp = await client.put("/api/auth/me", params={"first_name": "Updated"}, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        assert admin_user.first_name == "Updated"


class TestAuthChangePassword:
    async def test_change_password_success(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/auth/change-password", json={
            "old_password": "adminpass",
            "new_password": "newadminpass",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "password_changed"

    async def test_change_password_wrong_old(self, client, admin_user, admin_token, session):
        resp = await client.post("/api/auth/change-password", json={
            "old_password": "wrongpass",
            "new_password": "newpass",
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 401


class TestAuthLogout:
    async def test_logout(self, client, session):
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"
