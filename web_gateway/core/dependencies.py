from fastapi import Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .database import get_db
from .exceptions import ForbiddenException, UnauthorizedException
from .rbac import has_permission
from .security import decode_access_token
from ..models import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None),
) -> User:
    token = access_token
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise UnauthorizedException("Token manquant")
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedException("Token invalide ou expiré")
    user_id = int(payload.get("sub"))
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.role)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedException("Utilisateur introuvable ou inactif")
    return user


def require_role(resource: str, action: str):
    async def checker(current_user: User = Depends(get_current_user)):
        if not has_permission(current_user.role.name, resource, action):
            raise ForbiddenException(
                f"Action '{action}' sur '{resource}' non autorisée pour le rôle {current_user.role.name}"
            )
        return current_user
    return checker
