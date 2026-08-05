"""Portal settings."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AppSetting, User
from app.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])
settings = get_settings()


async def _get_kv(db: AsyncSession, key: str, default: str = "") -> str:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    if row and row.value is not None:
        return row.value
    return default


async def _set_kv(db: AsyncSession, key: str, value: str | None):
    if value is None:
        return
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


@router.get("", response_model=SettingsOut)
async def get_portal_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    public_ip = await _get_kv(db, "public_ip", os.getenv("PUBLIC_IP") or settings.public_ip)
    sip_pass = await _get_kv(
        db, "aibots_sip_password", os.getenv("AIBOTS_SIP_PASSWORD") or settings.aibots_sip_password
    )
    vic_url = await _get_kv(db, "vicidial_url", settings.vicidial_url)
    vic_user = await _get_kv(db, "vicidial_user", settings.vicidial_user)
    tdid = await _get_kv(db, "default_transfer_did", "")
    return SettingsOut(
        public_ip=public_ip,
        aibots_sip_password=sip_pass,
        sip_port=5060,
        vicidial_url=vic_url,
        vicidial_user=vic_user,
        default_transfer_did=tdid,
        admin_email=settings.admin_email,
        notes=[
            "These values feed the SIP Carrier page and campaign dialplan generators.",
            "After changing PUBLIC_IP or SIP password, update /opt/aibots/.env and: docker compose up -d --force-recreate asterisk",
            "VICIdial only needs carriers, remote agents, and virtual DIDs — no scripts.",
        ],
    )


@router.put("", response_model=SettingsOut)
async def update_portal_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        await _set_kv(db, k, v)
    await db.flush()
    return await get_portal_settings(db, user)
