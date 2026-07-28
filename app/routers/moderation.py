from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.core.deps import get_db, get_current_moderator
from app.models.report import Report, ReportStatus, TIER_1_REASONS, TIER_2_REASONS
from app.models.user import User, UserStatus
from app.models.banned_contact import BannedContact
from app.schemas.moderation import ModerationAction

router = APIRouter()


def _severity_rank(reason):
    if reason in TIER_1_REASONS:
        return 0
    if reason in TIER_2_REASONS:
        return 1
    return 2


@router.get("/audit")
async def get_audit_log(db: Session = Depends(get_db), _mod=Depends(get_current_moderator)):
    reports = (
        db.query(Report)
        .filter(Report.status == ReportStatus.resolved)
        .order_by(Report.resolved_at.desc())
        .all()
    )
    return reports


@router.get("/queue")
async def get_queue(db: Session = Depends(get_db), _mod=Depends(get_current_moderator)):
    reports = (
        db.query(Report)
        .filter(Report.status.in_([ReportStatus.open, ReportStatus.under_review]))
        .all()
    )
    reports.sort(key=lambda r: (_severity_rank(r.reason), r.created_at))
    return reports


@router.get("/case/{report_id}")
async def get_case(report_id: str, db: Session = Depends(get_db), _mod=Depends(get_current_moderator)):
    report = db.query(Report).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    reported_user = db.query(User).get(report.reported_user_id)
    prior_reports_against = (
        db.query(Report).filter(Report.reported_user_id == report.reported_user_id).count()
    )
    prior_reports_filed_by_reporter = (
        db.query(Report).filter(Report.reporter_id == report.reporter_id).count()
    )

    return {
        "report": report,
        "reported_user": {
            "id": str(reported_user.id),
            "handle": reported_user.handle,
            "created_at": reported_user.created_at,
            "strikes": reported_user.strikes,
            "status": reported_user.status,
        },
        "prior_reports_against_user": prior_reports_against,
        "prior_reports_filed_by_this_reporter": prior_reports_filed_by_reporter,
    }


@router.post("/case/{report_id}/action")
async def take_action(
    report_id: str,
    payload: ModerationAction,
    db: Session = Depends(get_db),
    mod=Depends(get_current_moderator),
):
    if not payload.note or not payload.note.strip():
        # Mandatory audit trail — no closing a case without a reason on record.
        raise HTTPException(status_code=400, detail="A note is required to close a case.")

    report = db.query(Report).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    reported_user = db.query(User).get(report.reported_user_id)

    if payload.action == "dismiss":
        pass  # no change to user status

    elif payload.action == "remove_content":
        # Content removal handled by post/message service based on report.post_id/thread_id
        pass

    elif payload.action == "remove_and_strike":
        reported_user.strikes += 1
        if reported_user.strikes >= 3:
            reported_user.status = UserStatus.banned

    elif payload.action == "remove_and_ban":
        reported_user.status = UserStatus.banned
        db.add(BannedContact(
            contact_ref_hash=reported_user.contact_ref_hash,
            reason=f"Tier action via report {report.id}: {payload.note[:200]}",
            banned_by_mod_id=mod.id,
        ))

    elif payload.action == "remove_ban_and_report_ncmec":
        reported_user.status = UserStatus.banned
        db.add(BannedContact(
            contact_ref_hash=reported_user.contact_ref_hash,
            reason=f"CSAM - report {report.id}",
            banned_by_mod_id=mod.id,
        ))
        from app.services.csam_response import file_ncmec_report
        await file_ncmec_report(db, report)

    else:
        raise HTTPException(status_code=400, detail="Unknown action.")

    report.status = ReportStatus.resolved
    report.resolved_at = datetime.utcnow()
    report.mod_action = payload.action
    report.mod_note = payload.note
    report.mod_id = mod.id

    db.commit()
    return {"message": "Case closed.", "action": payload.action}
