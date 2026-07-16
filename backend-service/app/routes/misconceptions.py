from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.misconception import MisconceptionLog
from app.models.user import User

router = APIRouter(prefix="/misconceptions", tags=["Misconceptions"])


class MisconceptionLogRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=50)
    sub_topic: str = Field(..., min_length=1, max_length=100)
    error_pattern: str = Field(..., min_length=1, max_length=255)


@router.post("/log")
async def log_misconception(
    payload: MisconceptionLogRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Log a specific error pattern for a student."""
    log_entry = MisconceptionLog(
        user_id=current_user.id,
        subject=payload.subject,
        sub_topic=payload.sub_topic,
        error_pattern=payload.error_pattern,
    )
    db.add(log_entry)
    await db.commit()
    return {"status": "success", "message": "Misconception logged."}


@router.get("/heatmap")
async def get_misconception_heatmap(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a heatmap of the user's misconceptions grouped by subject and sub-topic."""
    result = await db.execute(
        select(
            MisconceptionLog.subject,
            MisconceptionLog.sub_topic,
            func.count(MisconceptionLog.id).label("error_count"),
        )
        .where(MisconceptionLog.user_id == current_user.id)
        .group_by(MisconceptionLog.subject, MisconceptionLog.sub_topic)
        .order_by(func.count(MisconceptionLog.id).desc())
    )

    heatmap = [
        {
            "subject": row.subject,
            "sub_topic": row.sub_topic,
            "error_count": row.error_count,
        }
        for row in result.all()
    ]

    return {"data": heatmap}
