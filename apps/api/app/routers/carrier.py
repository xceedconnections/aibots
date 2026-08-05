from fastapi import APIRouter, Depends
from pydantic import BaseModel
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import AppSetting, User, VicidialServer
from app.services.asterisk_sync import vicidial_ip_peer_snippet

router = APIRouter(prefix="/carrier", tags=["carrier"])
settings = get_settings()


class CarrierConfig(BaseModel):
    mode: str = "ip_carrier"
    public_ip: str
    sip_host: str
    sip_port: int = 5060
    sip_username: str = "aibots"
    sip_password: str = ""
    vicidial_ip: str
    closer_hint: str
    vicidial_carrier_account_entry: str
    vicidial_carrier_protocol: str
    vicidial_carrier_globals: str
    vicidial_ai_carrier_dialplan: str
    vicidial_transfer_carrier_dialplan: str
    vicidial_server_ip_peer: str
    allowed_vicidial_ips: list[str]
    vicidial_steps: list[str]
    notes: list[str]


@router.get("/config", response_model=CarrierConfig)
async def carrier_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    public_row = (
        await db.execute(select(AppSetting).where(AppSetting.key == "public_ip"))
    ).scalar_one_or_none()
    public_ip = (public_row.value if public_row and public_row.value else None) or os.getenv(
        "PUBLIC_IP"
    ) or settings.public_ip

    servers = (
        await db.execute(
            select(VicidialServer).where(VicidialServer.active == True).order_by(VicidialServer.id)  # noqa: E712
        )
    ).scalars().all()
    allowed = []
    for s in servers:
        ip = (s.sip_ip or s.host or "").strip()
        if ip and ip not in allowed:
            allowed.append(ip)
    if not allowed:
        seed = settings.asterisk_ami_host
        if seed and seed not in ("127.0.0.1", "YOUR_VICIDIAL_IP"):
            allowed.append(seed)

    vicidial_ip = allowed[0] if allowed else "YOUR_VICIDIAL_IP"

    ai_dialplan = f"""exten => _27001,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,AGI(agi-set_variables.agi,)
same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${{lead_id}})
same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${{phone_number}})
same => n,SIPAddHeader(X-VICIdial-Client-Id: CID_0006-a)
same => n,SIPAddHeader(X-VICIdial-User-Id: 27001)
same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${{campaign_id}})
same => n,Dial(SIP/aibots/27001,60,tT)
same => n,Hangup()

exten => _27002,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,AGI(agi-set_variables.agi,)
same => n,SIPAddHeader(X-VICIdial-Lead-Id: ${{lead_id}})
same => n,SIPAddHeader(X-VICIdial-Caller-Id: ${{phone_number}})
same => n,SIPAddHeader(X-VICIdial-Client-Id: CID_0006-b)
same => n,SIPAddHeader(X-VICIdial-User-Id: 27016)
same => n,SIPAddHeader(X-VICIdial-Campaign-Id: ${{campaign_id}})
same => n,Dial(SIP/aibots/27002,60,tT)
same => n,Hangup()"""

    xfer_dialplan = """exten => _37000,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027001)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()

exten => _67000,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027001)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()

exten => _67001,1,AGI(agi://127.0.0.1:4577/call_log)
same => n,Set(DID=106027002)
same => n,Dial(SIP/Ctransfer1/${DID},,tTor)
same => n,Hangup()"""

    peer = vicidial_ip_peer_snippet(public_ip)

    return CarrierConfig(
        mode="ip_carrier",
        public_ip=public_ip,
        sip_host=public_ip,
        sip_port=5060,
        sip_username="aibots",
        sip_password="",
        vicidial_ip=vicidial_ip,
        closer_hint="Create virtual DIDs (e.g. 106027001) routed to closer in-groups. Set bot Transfer DID to match.",
        vicidial_carrier_account_entry="AIBOTS",
        vicidial_carrier_protocol="SIP",
        vicidial_carrier_globals="SIP/aibots",
        vicidial_ai_carrier_dialplan=ai_dialplan,
        vicidial_transfer_carrier_dialplan=xfer_dialplan,
        vicidial_server_ip_peer=peer,
        allowed_vicidial_ips=allowed,
        vicidial_steps=[
            "Install AIBOTS first — add Vicidial servers in Portal → VICIdial Servers (PUBLIC SIP IP).",
            "On Vicidial Asterisk: paste IP peer [aibots] host=AIBOTS_PUBLIC_IP type=peer insecure=port,invite.",
            "Admin → Carriers → dialplan with X-VICIdial headers and Dial(SIP/aibots) — peer host= is enough.",
            "Create remote agents + virtual DIDs → closer in-groups.",
            "Assign carrier to campaign. No scripts. No register lines.",
        ],
        notes=[
            "Carriers are IP-based (same as commercial AI bots) — not SIP registration.",
            "Portal sip_ip must be the Vicibox PUBLIC address AIBOTS sees on UDP/5060.",
            "Firewall allow-list drops wrong IPs (empty Calls + no bot audio). Use AIBOTS_SIP_OPEN=1 to debug.",
            "Open UDP 5060 + RTP 10000-10100 from each Vicidial IP to AIBOTS.",
        ],
    )
