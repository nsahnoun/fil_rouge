# Architecture

## System Overview

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│   Browser   │────▶│   nginx:80   │────▶│  Gateway  │
│  (Canvas)   │     │  (reverse    │     │  :8001    │
│             │◀────│   proxy)     │◀────│           │
└─────────────┘     └──────────────┘     └────┬──────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  ceph_api:8000     │
                                    │  (AI landmark      │
                                    │   prediction)      │
                                    └───────────────────┘
```

## Component Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| Web framework | FastAPI 0.136.1 | Async Python web framework |
| ORM | SQLAlchemy 2.0.49 | Async with aiosqlite |
| Database | SQLite | File-based, zero-config |
| Auth | JWT (python-jose) + bcrypt | HttpOnly cookies + Bearer tokens |
| Templates | Jinja2 3.1.6 | Server-side rendered pages |
| PDF | WeasyPrint 68.1 | Clinical report generation |
| Canvas | Vanilla JS | Cephalometric tracing engine |
| Proxy | nginx | Rate limiting, static cache, SSL |
| Cache | Redis | Session store, rate limiter backend |

## Data Flow

### Authentication
```
Client ──POST /api/auth/register──▶ Gateway ──Create User──▶ DB
Client ◀───{access_token, cookie}── Gateway
Client ──GET /api/auth/me (Cookie/Bearer)──▶ Gateway ──JWT decode──▶ DB lookup──▶ Response
```

### Analysis Pipeline
```
Upload ──▶ Save image ──▶ ceph_api /predict ──▶ Store landmarks ──▶ Canvas edit ──▶ Validate ──▶ Report PDF
```

## Database Schema

26 tables organized into domains:

- **Identity**: `roles`, `users`, `user_sessions`, `user_preferences`
- **Clinical**: `patients`, `patient_documents`, `clinical_notes`, `consent_logs`
- **Imaging**: `radios`
- **Analysis**: `analyses`, `analysis_comparisons`, `review_requests`
- **Reporting**: `reports`, `report_templates`
- **Operations**: `audit_logs`, `tasks`, `notifications`, `clinic_settings`

## RBAC Model

| Role | Permissions |
|------|------------|
| Admin | Full access to all resources |
| Orthodontist | Patient CRUD, analysis full, report sign/send |
| Assistant | Patient create/read/update, analysis/report read, task update |
| Intern | Patient/analysis/report read-only |

## Security

- JWT tokens with 24h expiry in HttpOnly cookies
- Password hashing with bcrypt (12 rounds)
- RBAC enforced at router level via `require_role()` dependency
- Nginx rate limiting (30 req/s general, 5 req/s auth)
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options
- SQL injection prevention via SQLAlchemy parameterized queries

## Performance

- Async I/O throughout (asyncpg/aiosqlite, httpx for upstream calls)
- Nginx static file caching (1y max-age for assets)
- Server-side template rendering (no CSR waterfall)
- No WebSocket or Celery for MVP — BackgroundTasks only
