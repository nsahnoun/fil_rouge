from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..core.exceptions import ConflictException, NotFoundException, UnauthorizedException
from ..core.security import create_access_token, decode_access_token, hash_password, verify_password
from ..models import Role, User, UserSession

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise ConflictException("Email déjà utilisé")
    role_result = await db.execute(select(Role).where(Role.name == "intern"))
    default_role = role_result.scalar_one_or_none()
    user_count = await db.execute(select(User))
    is_first = user_count.scalar() is None
    if is_first:
        admin_role = await db.execute(select(Role).where(Role.name == "admin"))
        default_role = admin_role.scalar_one_or_none()
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        role_id=default_role.id,
    )
    db.add(user)
    await db.flush()
    token = create_access_token(user.id, default_role.name)
    return {"access_token": token, "user_id": user.id, "role": default_role.name}


@router.post("/login")
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email).options(selectinload(User.role)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise UnauthorizedException("Email ou mot de passe incorrect")
    if not user.is_active:
        raise UnauthorizedException("Compte désactivé")
    user.last_login = datetime.now(timezone.utc)
    token = create_access_token(user.id, user.role.name)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400 * 24,
        samesite="lax",
    )
    return {"access_token": token, "user_id": user.id, "role": user.role.name, "name": f"{user.first_name} {user.last_name}"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "logged_out"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role.name,
        "speciality": current_user.speciality,
        "license_number": current_user.license_number,
        "is_active": current_user.is_active,
    }


@router.put("/me")
async def update_me(
    first_name: str | None = None,
    last_name: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if first_name:
        current_user.first_name = first_name
    if last_name:
        current_user.last_name = last_name
    await db.flush()
    return {"status": "updated"}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.old_password, current_user.password_hash):
        raise UnauthorizedException("Ancien mot de passe incorrect")
    current_user.password_hash = hash_password(req.new_password)
    await db.flush()
    return {"status": "password_changed"}
