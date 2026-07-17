import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
settings = get_settings()


async def _ensure_admin(db: AsyncSession) -> None:
    """Create admin from env if no users exist (recovery after failed seed)."""
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return
    admin = User(
        email=settings.admin_email,
        hashed_password=hash_password(settings.admin_password),
        full_name="Admin",
    )
    db.add(admin)
    await db.flush()
    logger.warning("Auto-created admin user %s (no users in database)", settings.admin_email)


async def _authenticate(email: str, password: str, db: AsyncSession) -> User:
    email = (email or "").strip()
    await _ensure_admin(db)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await _authenticate(form_data.username, form_data.password, db)
        return TokenResponse(access_token=create_access_token(user.email))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Login failed")
        raise HTTPException(status_code=500, detail=f"Login error: {exc}") from exc


@router.post("/login/json", response_model=TokenResponse)
async def login_json(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await _authenticate(payload.email, payload.password, db)
        return TokenResponse(access_token=create_access_token(user.email))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Login JSON failed")
        raise HTTPException(status_code=500, detail=f"Login error: {exc}") from exc


@router.post("/reset-admin", response_model=UserOut)
async def reset_admin(db: AsyncSession = Depends(get_db)):
    """
    Reset admin password from ADMIN_EMAIL / ADMIN_PASSWORD env.
    Intended for initial setup / recovery on a private server.
    """
    result = await db.execute(select(User).where(User.email == settings.admin_email))
    user = result.scalar_one_or_none()
    if user:
        user.hashed_password = hash_password(settings.admin_password)
        user.is_active = True
    else:
        user = User(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            full_name="Admin",
        )
        db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
