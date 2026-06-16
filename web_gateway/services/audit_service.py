import json
import logging

from ..core.database import async_session
from ..models import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    try:
        async with async_session() as session:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        logger.error(f"Audit log failed: {e}")
