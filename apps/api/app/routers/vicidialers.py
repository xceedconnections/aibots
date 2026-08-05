"""VICIdial dialer server registry — IP-based trunks (no SIP registration)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User, VicidialServer
from app.schemas import VicidialServerCreate, VicidialServerOut, VicidialServerUpdate
from app.services.asterisk_sync import rebuild_asterisk_identify, vicidial_ip_peer_snippet

router = APIRouter(prefix="/vicidialers", tags=["vicidialers"])


class VicidialerDetail(VicidialServerOut):
    aibots_peer_snippet: str = ""
    carrier_globals: str = ""
    note: str = "IP-based peer — no SIP registration on Vicidial or AIBOTS"


class IdentifySyncOut(BaseModel):
    content: str
    path: str


@router.get("", response_model=list[VicidialServerOut])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(VicidialServer).order_by(VicidialServer.id.desc()))
    return result.scalars().all()


@router.post("/sync-asterisk", response_model=IdentifySyncOut)
async def sync_asterisk(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    content = await rebuild_asterisk_identify(db)
    return IdentifySyncOut(
        content=content,
        path=os.getenv("ASTERISK_IDENTIFY_PATH", "/data/asterisk/pjsip_identify.conf"),
    )


@router.post("", response_model=VicidialerDetail, status_code=201)
async def create_server(
    payload: VicidialServerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data = payload.model_dump()
    if not data.get("sip_ip"):
        data["sip_ip"] = data["host"]
    row = VicidialServer(**data)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await rebuild_asterisk_identify(db)
    public_ip = os.getenv("PUBLIC_IP", "YOUR_AIBOTS_IP")
    return VicidialerDetail(
        **VicidialServerOut.model_validate(row).model_dump(),
        aibots_peer_snippet=vicidial_ip_peer_snippet(public_ip),
        carrier_globals=f"SIP/aibots@{public_ip}",
    )


@router.get("/{server_id}", response_model=VicidialerDetail)
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = (
        await db.execute(select(VicidialServer).where(VicidialServer.id == server_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Server not found")
    public_ip = os.getenv("PUBLIC_IP", "YOUR_AIBOTS_IP")
    return VicidialerDetail(
        **VicidialServerOut.model_validate(row).model_dump(),
        aibots_peer_snippet=vicidial_ip_peer_snippet(public_ip),
        carrier_globals=f"SIP/aibots@{public_ip}",
    )


@router.patch("/{server_id}", response_model=VicidialServerOut)
async def update_server(
    server_id: int,
    payload: VicidialServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = (
        await db.execute(select(VicidialServer).where(VicidialServer.id == server_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Server not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    await rebuild_asterisk_identify(db)
    return row


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = (
        await db.execute(select(VicidialServer).where(VicidialServer.id == server_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Server not found")
    await db.delete(row)
    await db.flush()
    await rebuild_asterisk_identify(db)
