# Developer Guide

## Environment Setup

```bash
git clone <repo>
cd fil_rouge/web_gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure environment variables in `.env`:

```env
DATABASE_URL=sqlite+aiosqlite:///data/ceph.db
SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
CEPH_API_URL=http://localhost:8000
```

## Run Dev Server

```bash
uvicorn web_gateway.app:app --reload --port 8001
```

The API docs are available at `http://localhost:8001/docs`.

## Testing

### Run all tests

```bash
python3 -m pytest web_gateway/tests/ --asyncio-mode=auto
```

### With coverage

```bash
python3 -m pytest web_gateway/tests/ --asyncio-mode=auto --cov=web_gateway --cov-report=term
```

### Run specific test file

```bash
python3 -m pytest web_gateway/tests/test_auth.py --asyncio-mode=auto -v
```

### Test architecture

- **conftest.py**: In-memory SQLite, transaction rollback per test, fixture-based data setup
- 128 tests across 11 files targeting >92% code coverage
- Async tests with `httpx.AsyncClient(ASGITransport(app=app))`

## Project Conventions

### Code style

- Type hints required for all function signatures
- No comments in code (self-documenting via types and naming)
- `ruff` for linting (config in pyproject.toml)
- Max line length: 120

### Router pattern

```python
router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/resource")
async def list_resource(db: AsyncSession = Depends(get_db)):
    ...

@router.post("/resource", dependencies=[Depends(require_role("resource", "create"))])
async def create_resource(req: PydanticModel, db: AsyncSession = Depends(get_db)):
    ...
```

### Model pattern

```python
class MyModel(Base):
    __tablename__ = "my_models"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=_utcnow)
```

### Dependency injection

- `get_db` → provides AsyncSession with auto-commit/rollback
- `get_current_user` → extracts user from JWT (Cookie or Bearer)
- `require_role(resource, action)` → checks RBAC

## Adding a New Resource

1. Add model in `models.py`
2. Create router in `routers/` with CRUD endpoints
3. Register router in `app.py`
4. Add service logic in `services/` if needed
5. Write tests in `tests/`
6. Run tests and verify coverage

## Docker

```bash
# Build and run all services
docker compose up --build

# Rebuild single service
docker compose build web_gateway
```

## Database Migrations

The current setup uses SQLAlchemy `create_all()` on startup. For production:

1. Install Alembic: `pip install alembic`
2. `alembic init alembic`
3. Configure `alembic/env.py` with `async_engine`
4. Generate migrations: `alembic revision --autogenerate -m "description"`
5. Apply: `alembic upgrade head`
