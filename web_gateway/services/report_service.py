import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..core.config import settings

logger = logging.getLogger(__name__)

template_dir = Path(__file__).parent.parent / "templates" / "reports"
jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))


async def generate_pdf(
    report_id: int,
    patient: dict,
    analysis: dict,
    measurements: dict,
    orthodontist: dict,
    clinic: dict | None = None,
    signature_image: str | None = None,
) -> str | None:
    try:
        clinic = clinic or {
            "name": settings.clinic_name,
            "city": settings.clinic_city,
            "logo": "",
            "address": "",
        }
        template = jinja_env.get_template("clinical_report.html")
        html = template.render(
            clinic=clinic,
            patient=patient,
            analysis=analysis,
            measurements=measurements,
            orthodontist=orthodontist,
            signature_image=signature_image or "",
            today=datetime.now(),
        )

        from weasyprint import HTML
        pdf_path = settings.report_path / f"report_{report_id}.pdf"
        HTML(string=html).write_pdf(target=str(pdf_path))
        return str(pdf_path)
    except Exception as e:
        logger.error(f"PDF generation failed for report {report_id}: {e}")
        return None
