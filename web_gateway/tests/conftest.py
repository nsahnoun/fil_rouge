import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from httpx import ASGITransport
import pytest
import pytest_asyncio
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from web_gateway.core.database import Base, get_db
from web_gateway.core.security import create_access_token, hash_password
from web_gateway.models import (
    Analysis, AuditLog, ClinicSetting, ClinicalNote, ConsentLog,
    Notification, Patient, PatientDocument, Radio, Report, ReportTemplate,
    ReviewRequest, Role, Task, User, UserPreference, UserSession,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_here = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    connection = await engine.connect()
    transaction = await connection.begin()
    async_session_local = async_sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_local() as s:
        yield s
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def roles(session):
    roles_data = [
        ("admin", '{"all":["*"]}'),
        ("orthodontist", '{"patients":["read","write","analyze"],"reports":["generate","sign"],"analyses":["full"]}'),
        ("assistant", '{"patients":["read","write"],"analyses":["read"],"reports":["read"]}'),
        ("intern", '{"patients":["read"],"analyses":["read"],"reports":["read"]}'),
    ]
    result = {}
    for name, perms in roles_data:
        r = Role(name=name, permissions=perms)
        session.add(r)
        await session.flush()
        result[name] = r
    return result


@pytest_asyncio.fixture
async def admin_user(session, roles):
    u = User(
        email="admin@test.com",
        password_hash=hash_password("adminpass"),
        first_name="Admin",
        last_name="User",
        role_id=roles["admin"].id,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    u.role = roles["admin"]
    return u


@pytest_asyncio.fixture
async def ortho_user(session, roles):
    u = User(
        email="ortho@test.com",
        password_hash=hash_password("orthopass"),
        first_name="Ortho",
        last_name="Doc",
        role_id=roles["orthodontist"].id,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    u.role = roles["orthodontist"]
    return u


@pytest_asyncio.fixture
async def assistant_user(session, roles):
    u = User(
        email="assist@test.com",
        password_hash=hash_password("assistpass"),
        first_name="Assist",
        last_name="Ant",
        role_id=roles["assistant"].id,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    u.role = roles["assistant"]
    return u


@pytest_asyncio.fixture
async def intern_user(session, roles):
    u = User(
        email="intern@test.com",
        password_hash=hash_password("internpass"),
        first_name="Intern",
        last_name="Student",
        role_id=roles["intern"].id,
        is_active=True,
    )
    session.add(u)
    await session.flush()
    u.role = roles["intern"]
    return u


@pytest_asyncio.fixture
async def patient(session, ortho_user, roles):
    p = Patient(
        first_name="Jean",
        last_name="Dupont",
        birth_date=date(1990, 5, 15),
        gender="M",
        email="jean@test.com",
        phone="0123456789",
        created_by=ortho_user.id,
        assigned_to=ortho_user.id,
    )
    session.add(p)
    await session.flush()
    return p


@pytest_asyncio.fixture
async def radio(session, patient, ortho_user):
    r = Radio(
        patient_id=patient.id,
        uploaded_by=ortho_user.id,
        filename="ceph.png",
        file_path="/tmp/ceph_test_nonexistent_xyz.png",
        mime_type="image/png",
        acquisition_date=date.today(),
    )
    session.add(r)
    await session.flush()
    return r


@pytest_asyncio.fixture
async def analysis(session, radio, ortho_user):
    a = Analysis(
        radio_id=radio.id,
        performed_by=ortho_user.id,
        landmarks=json.dumps([{"name": "N", "x": 100, "y": 200}]),
        measurements=json.dumps({"SNA": 82.0, "SNB": 80.0}),
        status="draft",
    )
    session.add(a)
    await session.flush()
    return a


@pytest_asyncio.fixture
async def client(session):
    from web_gateway.app import app

    async def _override():
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

    app.dependency_overrides[get_db] = _override
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(admin_user):
    return create_access_token(admin_user.id, "admin")


@pytest_asyncio.fixture
async def ortho_token(ortho_user):
    return create_access_token(ortho_user.id, "orthodontist")


@pytest_asyncio.fixture
async def intern_token(intern_user):
    return create_access_token(intern_user.id, "intern")


@pytest_asyncio.fixture
async def assistant_token(assistant_user):
    return create_access_token(assistant_user.id, "assistant")
