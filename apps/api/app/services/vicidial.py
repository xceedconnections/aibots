"""VICIdial helpers — vendor mode uses SIP DID transfer (no Vicidial scripts)."""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def vicidial_api(function: str, params: dict) -> str:
    """Optional VICIdial non-agent API (lead updates). Not required for carrier mode."""
    base = settings.vicidial_url.rstrip("/")
    query = {
        "source": settings.vicidial_source,
        "user": settings.vicidial_user,
        "pass": settings.vicidial_pass,
        "function": function,
        **params,
    }
    url = f"{base}/non_agent_api.php?{urlencode(query)}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            text = resp.text
            logger.info("VICIdial API %s => %s", function, text[:200])
            return text
    except Exception as exc:
        logger.error("VICIdial API error: %s", exc)
        return f"ERROR: {exc}"


async def mark_sip_transfer(
    call_id: Optional[str],
    transfer_did: Optional[str],
    closer_campaign: Optional[str] = None,
) -> dict:
    """
    Vendor transfer: tell AIBOTS Asterisk dialplan to Dial() the virtual DID
    back to VICIdial after AudioSocket ends. No AMI on VICIdial required.
    """
    if not call_id:
        return {"ok": False, "reason": "missing call_id"}
    if not transfer_did:
        return {"ok": False, "reason": "missing transfer_did"}

    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        payload = {
            "action": "transfer",
            "transfer_did": transfer_did,
            "closer_campaign": closer_campaign,
        }
        await r.setex(f"aibots:sip:{call_id}:action", 300, json.dumps(payload))
        # Plain text for Asterisk CURL dialplan
        await r.setex(f"aibots:sip:{call_id}:xfer", 300, transfer_did)
        logger.info("Marked SIP transfer uid=%s did=%s", call_id, transfer_did)
        return {"ok": True, "transfer_did": transfer_did, "mode": "sip_did"}
    finally:
        await r.aclose()


async def mark_sip_hangup(call_id: Optional[str]) -> dict:
    if not call_id:
        return {"ok": False}
    r = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.setex(f"aibots:sip:{call_id}:action", 300, json.dumps({"action": "hangup"}))
        await r.delete(f"aibots:sip:{call_id}:xfer")
        return {"ok": True, "action": "hangup"}
    finally:
        await r.aclose()


async def transfer_to_closer(
    phone: Optional[str] = None,
    lead_id: Optional[str] = None,
    campaign: Optional[str] = None,
    closer_campaign: Optional[str] = None,
    call_id: Optional[str] = None,
    transfer_did: Optional[str] = None,
) -> dict:
    """
    Primary path: SIP DID transfer via AIBOTS Asterisk dialplan.
    Optional: best-effort lead comment update if VICIdial API is configured.
    """
    sip = await mark_sip_transfer(
        call_id=call_id,
        transfer_did=transfer_did,
        closer_campaign=closer_campaign,
    )

    lead_update = None
    if lead_id and settings.vicidial_url and "YOUR_VICIDIAL" not in settings.vicidial_url:
        try:
            lead_update = await update_lead_fields(
                lead_id,
                {"comments": f"AIBOTS xfer DID={transfer_did} closer={closer_campaign}"[:255]},
            )
        except Exception as exc:
            lead_update = str(exc)

    return {
        "mode": "sip_did",
        "sip_transfer": sip,
        "lead_update": lead_update,
        "closer_campaign": closer_campaign,
        "transfer_did": transfer_did,
        "call_id": call_id,
        "lead_id": lead_id,
        "phone": phone,
        "campaign": campaign,
    }


async def update_lead_fields(lead_id: str, fields: dict) -> str:
    """Push qualification variables back onto the VICIdial lead (optional)."""
    params = {"lead_id": lead_id, **fields}
    return await vicidial_api("update_lead", params)
