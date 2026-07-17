"""VICIdial Agent API + Asterisk AMI helpers for call transfer."""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def vicidial_api(function: str, params: dict) -> str:
    """Call VICIdial non-agent API (api.php)."""
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


async def transfer_to_closer(
    phone: Optional[str] = None,
    lead_id: Optional[str] = None,
    campaign: Optional[str] = None,
    closer_campaign: Optional[str] = None,
    call_id: Optional[str] = None,
) -> dict:
    """
    Request transfer of a live call into a VICIdial closer campaign.

    Uses ra_call_control / transfer_conference style API when available.
    Falls back to logging the intent so the worker/AMI bridge can act.
    """
    params = {}
    if phone:
        params["phone_number"] = phone
    if lead_id:
        params["lead_id"] = lead_id
    if campaign:
        params["campaign_id"] = campaign
    if closer_campaign:
        params["ingrouproup_ingroup"] = closer_campaign
        params["ingroupgroup"] = closer_campaign
    if call_id:
        params["call_id"] = call_id

    # Primary: external transfer / ra_call_control if configured on VICIdial
    result = await vicidial_api("ra_call_control", {
        **params,
        "value": "TRANSFER",
        "agent_user": settings.vicidial_user,
    })

    ami_ok = await ami_redirect(call_id=call_id, closer_campaign=closer_campaign)

    return {
        "vicidial_response": result,
        "ami_redirect": ami_ok,
        "closer_campaign": closer_campaign,
        "call_id": call_id,
        "lead_id": lead_id,
    }


async def ami_redirect(call_id: Optional[str], closer_campaign: Optional[str]) -> bool:
    """
    Best-effort AMI Redirect. Requires AMI user configured on Asterisk.

    For production you will map closer_campaign → dialplan context/exten.
    """
    if not call_id or not closer_campaign:
        return False
    try:
        import socket

        host = settings.asterisk_ami_host
        port = settings.asterisk_ami_port
        user = settings.asterisk_ami_user
        secret = settings.asterisk_ami_secret

        def send(sock, msg: str):
            sock.sendall(msg.encode("utf-8"))

        with socket.create_connection((host, port), timeout=5) as sock:
            sock.settimeout(5)
            # Read banner
            sock.recv(1024)
            send(sock, f"Action: Login\r\nUsername: {user}\r\nSecret: {secret}\r\n\r\n")
            sock.recv(4096)
            # Redirect channel named by call_id / uniqueid — adjust for your dialplan
            action = (
                "Action: Redirect\r\n"
                f"Channel: {call_id}\r\n"
                "Context: aibots-transfer\r\n"
                f"Exten: {closer_campaign}\r\n"
                "Priority: 1\r\n"
                "\r\n"
            )
            send(sock, action)
            resp = sock.recv(4096).decode("utf-8", errors="ignore")
            send(sock, "Action: Logoff\r\n\r\n")
            logger.info("AMI Redirect response: %s", resp[:300])
            return "Success" in resp or "Response: Success" in resp
    except Exception as exc:
        logger.warning("AMI redirect skipped/failed: %s", exc)
        return False


async def update_lead_fields(lead_id: str, fields: dict) -> str:
    """Push qualification variables back onto the VICIdial lead."""
    params = {"lead_id": lead_id, **fields}
    return await vicidial_api("update_lead", params)
