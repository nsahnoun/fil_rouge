# CephAnalysis — Project Summary

## Professional Web Application for Cephalometric Analysis in Orthodontics

CephAnalysis is a full-stack web application that enables orthodontists to perform digital cephalometric analysis on radiograph images. The application combines AI-powered landmark detection with an interactive canvas for manual adjustments, supporting 12 analysis methods widely used in orthodontics.

### Key Features

- **AI Landmark Detection**: Automatic detection of 29 anatomical landmarks using a TensorFlow HRNet model
- **Interactive Canvas**: Drag-and-drop landmark editing with real-time measurement calculation
- **12 Analysis Methods**: Ricketts, Steiner, Downs, Tweed, McNamara, Bjork-Jarabak, Wits, Rakosi, Segner-Hasund, Eastman, ABO, Quick
- **Multi-User RBAC**: 4 roles (Admin, Orthodontist, Assistant, Intern) with granular permissions
- **Patient Management**: Full CRUD, document upload, clinical notes, consent tracking (GDPR)
- **Radiograph Management**: Upload, DICOM metadata, acquisition tracking
- **Analysis Workflow**: AI prediction → manual adjustment → peer review → validation
- **PDF Reports**: Clinical report generation with WeasyPrint (server-side) and jsPDF (client-side)
- **Audit Trail**: Comprehensive activity logging for compliance
- **REST API**: Documented endpoints via OpenAPI/Swagger
- **Responsive UI**: Dark/light theme, mobile-compatible canvas with touch support
- **Docker Deployment**: 4 services (gateway, ceph_api, redis, nginx)

### Architecture

```
┌──────────┐    ┌───────────┐    ┌──────────┐
│  Browser │───▶│   Nginx   │───▶│  Gateway │───▶ SQLite
│  (JS)    │◀───│  :80/443  │◀───│  :8001   │◀───┐
└──────────┘    └───────────┘    └────┬─────┘    │
                                       │          │
                                ┌──────▼──────┐   │
                                │  ceph_api    │───┘
                                │  :8000       │
                                │  (HRNet AI)  │
                                └─────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (async Python) |
| **Database** | SQLite / PostgreSQL (via SQLAlchemy 2.0) |
| **Auth** | JWT + bcrypt, HttpOnly cookies |
| **Frontend** | Jinja2 templates + Vanilla JS (no framework) |
| **Canvas** | HTML5 Canvas API |
| **PDF** | WeasyPrint + jsPDF |
| **AI Model** | TensorFlow HRNet-W64 |
| **Infrastructure** | Docker Compose (4 services) |

### Testing

- **Framework**: pytest + pytest-asyncio
- **Coverage**: 94%
- **Tests**: 12 test files, ~154 tests covering all modules

### Security

- SQL injection prevention via parameterized ORM queries
- XSS protection via Jinja2 auto-escaping
- CSRF protection via HttpOnly + SameSite cookies
- Password hashing with bcrypt (12 rounds)
- Nginx rate limiting (30 req/s general, 5 req/s auth)
- Security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
- RBAC with principle of least privilege

### Links

- **API Documentation**: `/docs` (Swagger UI)
- **Repository**: GitHub (internal)
- **License**: Internal use — CephAnalysis Platform
