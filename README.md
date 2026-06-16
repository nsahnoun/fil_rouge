# CephAnalysis Web Gateway

Professional web application for cephalometric analysis in orthodontics. Provides multi-user management, AI-assisted landmark detection, clinical workflow, PDF report generation, and audit tracking.

## Features

- **Multi-user RBAC**: Admin, Orthodontist, Assistant, Intern roles with granular permissions
- **Patient management**: Full CRUD, documents, clinical notes, consent tracking
- **Radiograph management**: Upload, DICOM metadata, acquisition tracking
- **Cephalometric analysis**: AI landmark detection via ceph_api, manual adjustment on canvas, 12 analysis methods (Ricketts, Steiner, Downs, etc.)
- **Analysis review**: Peer review workflow with validation pipeline
- **PDF reports**: Clinical report generation with WeasyPrint
- **Audit trail**: Full activity logging for compliance
- **REST API**: JSON endpoints for all resources

## Quick Start

### Prerequisites

- Python 3.14+
- Docker & Docker Compose (recommended)

### Docker (production)

```bash
docker compose up --build
```

Services: web_gateway (:8001), ceph_api (:8000), nginx (:80), redis (:6379)

### Local development

```bash
cd web_gateway
cp .env.example .env    # configure as needed
pip install -r requirements.txt
uvicorn web_gateway.app:app --reload --port 8001
```

### Run tests

```bash
python3 -m pytest web_gateway/tests/ --asyncio-mode=auto --cov=web_gateway
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design and component details.

## API Documentation

Interactive API docs at `/docs` when the server is running.

## User Guide

See [USER_GUIDE.md](USER_GUIDE.md) for clinical workflow walkthroughs.

## Development

See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for setup, testing, and contribution.

## Project Structure

```
web_gateway/
├── app.py                  # FastAPI application factory
├── models.py               # 26 SQLAlchemy models
├── core/                   # Config, DB, security, RBAC, logging
├── routers/                # API route handlers
│   ├── auth.py             # Authentication & user management
│   ├── patients.py         # Patient CRUD, documents, notes
│   ├── radios.py           # Radiograph upload & retrieval
│   ├── analyses.py         # Cephalometric analysis endpoints
│   ├── reports.py          # Report templates & generation
│   ├── users.py            # Admin user management
│   ├── admin.py            # Stats, audit, performance
│   └── pages.py            # Server-side Jinja2 page routes
├── services/               # Business logic layer
│   ├── ceph_client.py      # HTTP client for ceph_api
│   ├── audit_service.py    # Audit logging
│   └── report_service.py   # PDF generation with WeasyPrint
├── static/                 # JS canvas engine, CSS, images
├── templates/              # Jinja2 HTML templates
├── tests/                  # pytest test suite (128 tests, 92% coverage)
└── data/                   # SQLite DB, uploads, reports
```

## License

Internal use — CephAnalysis Platform
