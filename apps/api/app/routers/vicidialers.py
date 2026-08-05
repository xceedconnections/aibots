"""VICIdial dialer server registry — IP-based trunks (no SIP registration)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User, VicidialServer
from app.schemas import VicidialServerCreate, VicidialServerOut, VicidialServerUpdate
from app.services.asterisk_sync import rebuild_asterisk_identify, vicidial_ip_peer_snippet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vicidialers", tags=["vicidialers"])


class VicidialerDetail(VicidialServerOut):
    aibots_peer_snippet: str = ""
    carrier_globals: str = ""
    note: str = "IP-based peer — no SIP registration on Vicidial or AIBOTS"
    sync_warning: str = ""


class IdentifySyncOut(BaseModel):
    content: str
    path: str


def _to_out(row: VicidialServer) -> VicidialServerOut:
    return VicidialServerOut(
        id=row.id,
        name=row.name,
        host=row.host,
        sip_ip=row.sip_ip,
        api_url=row.api_url,
        api_user=row.api_user,
        api_pass=row.api_pass,
        notes=row.notes,
        active=bool(row.active),
        created_at=row.created_at or datetime.now(timezone.utc),
    )


def _detail(row: VicidialServer, sync_warning: str = "") -> VicidialerDetail:
    public_ip = os.getenv("PUBLIC_IP", "YOUR_AIBOTS_IP")
    base = _to_out(row)
    return VicidialerDetail(
        **base.model_dump(),
        aibots_peer_snippet=vicidial_ip_peer_snippet(public_ip),
        carrier_globals=f"SIP/aibots@{public_ip}",
        sync_warning=sync_warning,
    )


@router.get("", response_model=list[VicidialServerOut])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(VicidialServer).order_by(VicidialServer.id.desc()))
    return [_to_out(r) for r in result.scalars().all()]


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
    host = (data.get("host") or "").strip()
    if not host:
        raise HTTPException(400, "Host / IP is required")
    data["host"] = host
    data["sip_ip"] = (data.get("sip_ip") or host).strip()
    data["name"] = (data.get("name") or host).strip()
    data["created_at"] = datetime.now(timezone.utc)

    existing = (
        await db.execute(
            select(VicidialServer).where(
                (VicidialServer.host == data["host"]) | (VicidialServer.sip_ip == data["sip_ip"])
            )
        )
    ).scalars().first()
    if existing:
        raise HTTPException(
            400,
            f"A Vicidial server with this IP already exists (#{existing.id} {existing.name}). "
            "Edit/delete it, or use a different IP.",
        )

    try:
        row = VicidialServer(
            name=data["name"],
            host=data["host"],
            sip_ip=data["sip_ip"],
            api_url=data.get("api_url") or None,
            api_user=data.get("api_user") or None,
            api_pass=data.get("api_pass") or None,
            notes=data.get("notes") or None,
            active=bool(data.get("active", True)),
            created_at=data["created_at"],
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
    except Exception as exc:
        logger.exception("Create Vicidial server DB error")
        raise HTTPException(500, f"Database error: {exc}") from exc

    sync_warning = ""
    try:
        result = await rebuild_asterisk_identify(db)
        if str(result).startswith("ERROR:"):
            sync_warning = result.split("\n", 1)[0]
    except Exception as exc:
        logger.exception("Asterisk sync after create failed")
        sync_warning = str(exc)

    return _detail(row, sync_warning=sync_warning)


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
    return _detail(row)


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
    try:
        await rebuild_asterisk_identify(db)
    except Exception:
        logger.exception("Asterisk sync after update failed")
    return _to_out(row)


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
    try:
        await rebuild_asterisk_identify(db)
    except Exception:
        logger.exception("Asterisk sync after delete failed")
