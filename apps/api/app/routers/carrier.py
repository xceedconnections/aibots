from fastapi import APIRouter, Depends
from pydantic import BaseModel
import os

from app.auth import get_current_user
from app.config import get_settings
from app.models import User

router = APIRouter(prefix="/carrier", tags=["carrier"])
settings = get_settings()


class CarrierConfig(BaseModel):
    mode: str = "sip_carrier"
    public_ip: str
    sip_host: str
    sip_port: int = 5060
    sip_username: str = "aibots"
    sip_password: str
    vicidial_ip: str
    closer_hint: str
    vicidial_carrier_account_entry: str
    vicidial_carrier_protocol: str
    vicidial_carrier_globals: str
    vicidial_carrier_dialplan: str
    vicidial_server_ip_registration: str
    notes: list[str]


@router.get("/config", response_model=CarrierConfig)
async def carrier_config(_: User = Depends(get_current_user)):
    public_ip = os.getenv("PUBLIC_IP") or settings.public_ip
    sip_pass = os.getenv("AIBOTS_SIP_PASSWORD") or settings.aibots_sip_password
    vicidial_ip = settings.asterisk_ami_host or "YOUR_VICIDIAL_IP"

    dialplan_simple = (
        f"Dial(SIP/aibots@{public_ip}/${{EXTEN}},60,tTo)\n"
        f"# Or PJSIP: Dial(PJSIP/${{EXTEN}}@aibots-trunk,60,tTo)"
    )

    peer = (
        f"host={public_ip}\n"
        f"username=aibots\n"
        f"secret={sip_pass}\n"
        f"type=peer\n"
        f"context=trunkinbound\n"
        f"disallow=all\n"
        f"allow=ulaw\n"
        f"insecure=port,invite\n"
        f"nat=force_rport,comedia"
    )

    return CarrierConfig(
        mode="sip_carrier",
        public_ip=public_ip,
        sip_host=public_ip,
        sip_port=5060,
        sip_username="aibots",
        sip_password=sip_pass,
        vicidial_ip=vicidial_ip,
        closer_hint="Set bot Transfer campaign to your VICIdial closer/in-group name",
        vicidial_carrier_account_entry="AIBOTS",
        vicidial_carrier_protocol="SIP",
        vicidial_carrier_globals=f"SIP/aibots@{public_ip}",
        vicidial_carrier_dialplan=dialplan_simple,
        vicidial_server_ip_registration=peer,
        notes=[
            "Create a VICIdial Carrier pointing at this AIBOTS SIP host (like other AI vendors).",
            "Assign that carrier to your outbound campaign — no Start Call URL required.",
            "Map bot Campaign field to your VICIdial campaign id.",
            "Open UDP 5060 and RTP 10000-10100 on AIBOTS for your VICIdial IP.",
            "Portal test calls still use simulate mode without SIP.",
            "Set PUBLIC_IP and AIBOTS_SIP_PASSWORD in /opt/aibots/.env then recreate asterisk.",
        ],
    )
