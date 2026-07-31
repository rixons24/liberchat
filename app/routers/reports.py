from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_db, get_current_user
from app.core.rate_limit import limiter
from app.models.report import Report, MessageReport, ReportReason, ReportStatus, TIER_1_REASONS
from app.models.user import User, UserStatus
from app.models.dm import DMThread, Message
from app.models.media import Media
from app.schemas.report import ReportCreate

router = APIRouter()

REPEAT_REPORT_THRESHOLD = 3
REPEAT_REPORT_WINDOW_HOURS = 72


@router.post("/file")
@limiter.limit("20/hour")
async def file_report(
    request: Request,
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = Report(
        reporter_id=current_user.id,
        reported_user_id=payload.reported_user_id,
        post_id=payload.post_id,
        thread_id=payload.thread_id,
        reason=payload.reason,
        detail_text=payload.detail_text,
        status=ReportStatus.open,
    )
    db.add(report)
    db.flush()  # get report.id before commit

    # Freeze DM evidence tied to this report, if applicable.
    if payload.thread_id:
        msg_report = MessageReport(
            report_id=report.id,
            thread_id=payload.thread_id,
            reported_message_ids=payload.reported_message_ids or [],
            thread_snapshot=payload.thread_snapshot,  # reporter's client-submitted decrypted view
        )
        db.add(msg_report)

        # Freeze any referenced media so it survives session-end deletion.
        if payload.reported_message_ids:
            media_rows = (
                db.query(Media)
                .join(Message, Message.media_id == Media.id)
                .filter(Message.id.in_(payload.reported_message_ids))
                .all()
            )
            for m in media_rows:
                m.held_for_report = True

    reported_user = db.query(User).get(payload.reported_user_id)

    # Tier 1: immediate action, no waiting for human review to restrict the account.
    if payload.reason in TIER_1_REASONS:
        report.status = ReportStatus.under_review
        reported_user.status = UserStatus.suspended_dm

    # Repeat-report auto-suspend: independent of tier, catches volume abuse.
    recent_cutoff = datetime.utcnow() - timedelta(hours=REPEAT_REPORT_WINDOW_HOURS)
    recent_report_count = (
        db.query(func.count(func.distinct(Report.reporter_id)))
        .filter(
            Report.reported_user_id == payload.reported_user_id,
            Report.created_at >= recent_cutoff,
        )
        .scalar()
    )
    if recent_report_count >= REPEAT_REPORT_THRESHOLD:
        reported_user.status = UserStatus.suspended_dm

    reported_user.report_count = (reported_user.report_count or 0) + 1

    db.commit()
    return {"message": "Report filed.", "report_id": str(report.id)}
