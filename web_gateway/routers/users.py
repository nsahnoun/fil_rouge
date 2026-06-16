from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.dependencies import get_current_user, require_role
from ..core.exceptions import ConflictException, NotFoundException
from ..core.security import hash_password
from ..models import Role, User

router = APIRouter(dependencies=[Depends(require_role("users", "read"))])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role_name: str
    speciality: str | None = None
    license_number: str | None = None


@router.get("")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).options(selectinload(User.role)))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": u.role.name,
            "is_active": u.is_active,
            "last_login": u.last_login,
        }
        for u in users
    ]


@router.post("")
async def create_user(req: CreateUserRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("users", "create"))):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise ConflictException("Email déjà utilisé")
    role = await db.execute(select(Role).where(Role.name == req.role_name))
    role_obj = role.scalar_one_or_none()
    if not role_obj:
        raise NotFoundException("Rôle introuvable")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        role_id=role_obj.id,
        speciality=req.speciality,
        license_number=req.license_number,
        created_by=current_user.id,
    )
    db.add(user)
    await db.flush()
    return {"id": user.id, "email": user.email, "role": req.role_name}


@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.role)))
    u = result.scalar_one_or_none()
    if not u:
        raise NotFoundException("Utilisateur introuvable")
    return {
        "id": u.id,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "role": u.role.name,
        "speciality": u.speciality,
        "license_number": u.license_number,
        "is_active": u.is_active,
        "last_login": u.last_login,
        "created_at": u.created_at,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    role_name: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("users", "update")),
):
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.role)))
    u = result.scalar_one_or_none()
    if not u:
        raise NotFoundException("Utilisateur introuvable")
    if first_name is not None:
        u.first_name = first_name
    if last_name is not None:
        u.last_name = last_name
    if role_name is not None:
        role = await db.execute(select(Role).where(Role.name == role_name))
        role_obj = role.scalar_one_or_none()
        if not role_obj:
            raise NotFoundException("Rôle introuvable")
        u.role_id = role_obj.id
    if is_active is not None:
        u.is_active = is_active
    await db.flush()
    return {"status": "updated"}


@router.delete("/{user_id}")
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role("users", "delete"))):
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise NotFoundException("Utilisateur introuvable")
    u.is_active = False
    await db.flush()
    return {"status": "deactivated"}
