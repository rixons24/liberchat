from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.media import Media, MediaType, MediaScanStatus
from app.services import media_pipeline
from app.models.report import MessageReport

router = APIRouter()


@router.post("/upload")
async def upload_media(
    file: UploadFile,
    media_type: MediaType = Form(...),
    message_id: str = Form(...),
    duration_seconds: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted_bytes = await file.read()
    try:
        media = await media_pipeline.upload_media(
            db, message_id=message_id, media_type=media_type,
            encrypted_bytes=encrypted_bytes, duration_seconds=duration_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if media.scan_status == MediaScanStatus.flagged:
        raise HTTPException(status_code=403, detail="Content rejected.")
    if media.scan_status == MediaScanStatus.error:
        raise HTTPException(status_code=503, detail="Scan unavailable, try again.")

    return {"media_id": str(media.id), "status": media.scan_status}


@router.post("/{media_id}/view")
async def view_media(media_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    media = db.query(Media).get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    try:
        signed_url = await media_pipeline.start_view_session(db, media)
    except (PermissionError, ValueError) as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"signed_url": signed_url, "view_count": media.view_count}


@router.post("/{media_id}/heartbeat")
async def heartbeat(media_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    media = db.query(Media).get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    await media_pipeline.heartbeat_session(db, media)
    return {"ok": True}


@router.post("/{media_id}/end-session")
async def end_session(media_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    media = db.query(Media).get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")

    async def reporter_check(_media_id):
        # held_for_report is set directly on the Media row by the reports
        # router at the moment a report is filed — re-check it fresh here
        # in case a report came in between session start and session end.
        fresh = db.query(Media).get(str(_media_id))
        return bool(fresh and fresh.held_for_report)

    await media_pipeline.end_view_session(db, media, reporter_check=reporter_check)
    return {"status": media.lifecycle_status}
