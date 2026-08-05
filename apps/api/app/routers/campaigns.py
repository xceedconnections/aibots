"""Campaign overview — bots mapped as Vicidial AI campaigns with dialplan snippets."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AppSetting, Bot, User
from app.schemas import CampaignRow

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
settings = get_settings()


async def _public_ip(db: AsyncSession) -> str:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == "public_ip"))).scalar_one_or_none()
    if row and row.value:
        return row.value
    return os.getenv("PUBLIC_IP") or settings.public_ip


@router.get("", response_model=list[CampaignRow])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    public_ip = await _public_ip(db)
    bots = (await db.execute(select(Bot).order_by(Bot.id.desc()))).scalars().all()
    rows: list[CampaignRow] = []
    for b in bots:
        ra = b.remote_agent or "27001"
        cid = b.client_id or f"CID_BOT{b.id}"
        snippet = (
            f"exten => _{ra},1,AGI(agi://127.0.0.1:4577/call_log)\n"
            f"same => n,AGI(agi-set_variables.agi,)\n"
            f"same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${{lead_id}})\n"
            f"same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${{phone_number}})\n"
            f"same => n,SIPAddHeader(X-VICIdial-Client-Id: {cid})\n"
            f"same => n,SIPAddHeader(X-VICIdial-User-Id: {ra})\n"
            f"same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${{campaign_id}})\n"
            f"same => n,Dial(SIP/aibots@{public_ip})\n"
            f"same => n,Hangup()"
        )
        rows.append(
            CampaignRow(
                bot_id=b.id,
                name=b.name,
                campaign=b.campaign,
                client_id=b.client_id,
                remote_agent=b.remote_agent,
                transfer_did=b.transfer_did,
                transfer_campaign=b.transfer_campaign,
                active=b.active,
                dialplan_snippet=snippet,
            )
        )
    return rows
