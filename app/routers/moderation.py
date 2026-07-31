from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.core.deps import get_db, get_current_moderator
from app.models.report import Report, ReportStatus, TIER_1_REASONS, TIER_2_REASONS
from app.models.user import User, UserStatus
from app.models.banned_contact import BannedContact
from app.models.dm import DMThread
from app.schemas.moderation import ModerationAction, UserBanRequest

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

    def _remove_content():
        """Shared by every action that starts with 'remove_' — actually
        takes the content down, not just changing the user's status."""
        if report.post_id:
            from app.models.post import Post, PostStatus
            post = db.query(Post).get(report.post_id)
            if post:
                post.status = PostStatus.removed_by_mod
                post.deleted_at = datetime.utcnow()
        if report.thread_id:
            thread = db.query(DMThread).get(report.thread_id)
            if thread:
                thread.blocked = True

    if payload.action == "dismiss":
        pass  # no change to user status, no content removed

    elif payload.action == "remove_content":
        _remove_content()

    elif payload.action == "remove_and_strike":
        _remove_content()
        reported_user.strikes += 1
        if reported_user.strikes >= 3:
            reported_user.status = UserStatus.banned

    elif payload.action == "remove_and_ban":
        _remove_content()
        reported_user.status = UserStatus.banned
        db.add(BannedContact(
            contact_ref_hash=reported_user.contact_ref_hash,
            reason=f"Tier action via report {report.id}: {payload.note[:200]}",
            banned_by_mod_id=mod.id,
        ))

    elif payload.action == "remove_ban_and_report_ncmec":
        _remove_content()
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


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    _mod=Depends(get_current_moderator),
    limit: int = 100,
    offset: int = 0,
):
    total = db.query(User).count()
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return {
        "total": total,
        "users": [
            {
                "id": str(u.id),
                "handle": u.handle,
                "status": u.status,
                "created_at": u.created_at,
                "strikes": u.strikes,
                "report_count": u.report_count,
            }
            for u in users
        ],
    }


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    payload: UserBanRequest,
    db: Session = Depends(get_db),
    mod=Depends(get_current_moderator),
):
    """Direct ban outside the report-driven flow — for cases where a
    moderator spots something without a user report existing yet."""
    if not payload.note or not payload.note.strip():
        raise HTTPException(status_code=400, detail="A note is required to ban a user.")

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.status == UserStatus.banned:
        raise HTTPException(status_code=400, detail="User is already banned.")

    user.status = UserStatus.banned
    db.add(BannedContact(
        contact_ref_hash=user.contact_ref_hash,
        reason=f"Direct admin ban: {payload.note[:200]}",
        banned_by_mod_id=mod.id,
    ))
    db.commit()
    return {"message": f"User '{user.handle}' banned."}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _mod=Depends(get_current_moderator),
):
    """
    Hard delete — permanently removes the account and everything tied to
    it. Unlike ban, this does NOT add a banned_contacts entry, so the
    same phone number could sign up again. Use ban for abuse/policy
    violations; use delete for cleanup (test accounts, GDPR-style
    erasure requests, etc.).
    """
    from app.models.post import Post
    from app.models.dm import DMThread, Message
    from app.models.media import Media
    from app.models.report import MessageReport, Block, ThreadRead

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    thread_ids = [t.id for t in db.query(DMThread.id).filter(
        (DMThread.user_a_id == user.id) | (DMThread.user_b_id == user.id)
    ).all()]

    if thread_ids:
        db.query(MessageReport).filter(MessageReport.thread_id.in_(thread_ids)).delete(synchronize_session=False)
        message_ids = [m.id for m in db.query(Message.id).filter(Message.thread_id.in_(thread_ids)).all()]
        if message_ids:
            db.query(Media).filter(Media.message_id.in_(message_ids)).delete(synchronize_session=False)
        db.query(Message).filter(Message.thread_id.in_(thread_ids)).delete(synchronize_session=False)
        db.query(ThreadRead).filter(ThreadRead.thread_id.in_(thread_ids)).delete(synchronize_session=False)
        db.query(DMThread).filter(DMThread.id.in_(thread_ids)).delete(synchronize_session=False)

    db.query(Report).filter(
        (Report.reporter_id == user.id) | (Report.reported_user_id == user.id)
    ).delete(synchronize_session=False)
    db.query(Block).filter(
        (Block.blocker_id == user.id) | (Block.blocked_id == user.id)
    ).delete(synchronize_session=False)
    db.query(Post).filter_by(author_id=user.id).delete(synchronize_session=False)

    handle = user.handle
    db.delete(user)
    db.commit()
    return {"message": f"User '{handle}' permanently deleted."}
