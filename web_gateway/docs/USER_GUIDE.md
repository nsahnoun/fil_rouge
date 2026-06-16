# User Guide

## Roles & Access

| Role | Capabilities |
|------|-------------|
| Admin | Full access, user management, audit logs, system settings |
| Orthodontist | Full clinical workflow: patients, analyses, reports, signatures |
| Assistant | Patient intake, document upload, read-only access to analyses/reports |
| Intern | Read-only access to patients, analyses, and reports |

## Workflow

### 1. Patient Intake

1. Navigate to **Patients** → **New Patient**
2. Fill required fields (name, birth date)
3. Add optional: medical history, allergies, insurance, referring doctor
4. Assign to orthodontist
5. Upload consent form under **Documents**

### 2. Upload Radiograph

1. Open patient record → **Radios** tab
2. Click **Upload** and select cephalometric image
3. Enter acquisition date and laterality
4. Landmarks are automatically detected via AI

### 3. Cephalometric Analysis

1. From the radio view, click **Analyze**
2. The canvas loads with:
   - Detected landmarks (draggable)
   - Anatomical tracings (skull, vertebrae,软组织)
   - Current measurements
3. Adjust landmarks by dragging
4. Select analysis method (Ricketts, Steiner, Downs, etc.)
5. **Save** landmarks, **Export** as PNG/JSON/PDF

### 4. Review & Validation

- Submit analysis for peer review: **Request Review**
- Reviewer receives notification, can approve/reject with comments
- Once validated, analysis is locked and ready for reporting

### 5. Report Generation

1. Go to **Reports** → **Generate**
2. Select patient, analysis, and template
3. Report is generated as PDF with:
   - Patient demographics
   - Measurement tables (normal vs patient values)
   - Radiograph with traced landmarks
   - Orthodontist signature block
4. **Sign** the report digitally
5. Send to patient or referring doctor

## API Access

All API routes require authentication via:
- **Cookie**: `access_token` (set by login)
- **Bearer**: `Authorization: Bearer <token>`

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Authenticate |
| GET | `/api/auth/me` | Current user profile |
| GET | `/api/patients` | List patients |
| POST | `/api/patients` | Create patient |
| GET | `/api/patients/{id}` | Patient details |
| POST | `/api/radios/upload` | Upload radiograph |
| GET | `/api/analyses/{id}` | Get analysis with landmarks |
| POST | `/api/analyses/{id}/landmarks` | Update landmarks |
| POST | `/api/reports/generate` | Generate PDF report |
| GET | `/api/admin/stats` | Dashboard statistics (admin) |
| GET | `/api/admin/audit` | Audit log (admin) |

See `/docs` for full API reference.
