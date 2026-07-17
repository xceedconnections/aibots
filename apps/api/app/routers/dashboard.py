from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Bot, CallSession, CallStatus, User
from app.schemas import CallSessionOut, DashboardStats

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    bots_total = (await db.execute(select(func.count(Bot.id)))).scalar() or 0
    bots_active = (
        await db.execute(select(func.count(Bot.id)).where(Bot.active == True))  # noqa: E712
    ).scalar() or 0

    calls_today = (
        await db.execute(
            select(func.count(CallSession.id)).where(CallSession.started_at >= today_start)
        )
    ).scalar() or 0

    transfers_today = (
        await db.execute(
            select(func.count(CallSession.id)).where(
                CallSession.started_at >= today_start,
                CallSession.status == CallStatus.TRANSFERRED,
            )
        )
    ).scalar() or 0

    qualified_today = (
        await db.execute(
            select(func.count(CallSession.id)).where(
                CallSession.started_at >= today_start,
                CallSession.status.in_([CallStatus.QUALIFIED, CallStatus.TRANSFERRED]),
            )
        )
    ).scalar() or 0

    rejected_today = (
        await db.execute(
            select(func.count(CallSession.id)).where(
                CallSession.started_at >= today_start,
                CallSession.status == CallStatus.REJECTED,
            )
        )
    ).scalar() or 0

    avg_dur = (
        await db.execute(
            select(func.avg(CallSession.duration_seconds)).where(
                CallSession.started_at >= today_start,
                CallSession.duration_seconds > 0,
            )
        )
    ).scalar() or 0.0

    qual_rate = (qualified_today / calls_today * 100.0) if calls_today else 0.0

    return DashboardStats(
        bots_total=bots_total,
        bots_active=bots_active,
        calls_today=calls_today,
        transfers_today=transfers_today,
        qualified_today=qualified_today,
        rejected_today=rejected_today,
        avg_duration_seconds=float(avg_dur or 0),
        qualification_rate=round(qual_rate, 1),
    )


@router.get("/dashboard/recent-calls", response_model=list[CallSessionOut])
async def recent_calls(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CallSession).order_by(CallSession.id.desc()).limit(min(limit, 100))
    )
    return result.scalars().all()
