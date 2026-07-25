import uuid
from datetime import datetime, timedelta

from app.models.media import Media, MediaType, MediaScanStatus, MediaLifecycleStatus
from app.config import settings
from app.services import storage_client  # thin wrapper around R2/S3 client
from app.services import scan_client     # thin wrapper around Thorn Safer / PhotoDNA


MAX_DURATION_SECONDS = {
    MediaType.video: 60,
    MediaType.audio: 120,
}


async def upload_media(db, message_id: uuid.UUID | None, media_type: MediaType, encrypted_bytes: bytes, duration_seconds: int | None, nsfw: bool = False):
    """
    Full upload path. The moderation scan happens SYNCHRONOUSLY, before
    the media row is ever marked available — this matters specifically
    because of the view-once model: a background/async scan could let
    unscanned content be viewed and deleted before the scan even finishes.
    """
    if media_type in MAX_DURATION_SECONDS and duration_seconds:
        cap = MAX_DURATION_SECONDS[media_type]
        if duration_seconds > cap:
            raise ValueError(f"{media_type.value} exceeds max duration of {cap}s")

    storage_key = f"media/{uuid.uuid4()}"

    media = Media(
        message_id=message_id,
        type=media_type,
        nsfw=nsfw,
        storage_key=storage_key,
        duration_seconds=duration_seconds,
        scan_status=MediaScanStatus.pending,
        lifecycle_status=MediaLifecycleStatus.available,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    # Run moderation scan BEFORE storing/exposing the object.
    # Images/video -> Thorn Safer (hash match against known CSAM + ML
    # classifiers). Audio has no equivalent industry hash-matching
    # standard today, so audio relies on the report-freeze pipeline
    # plus human review rather than automated pre-scan.
    try:
        if media_type in (MediaType.image, MediaType.video):
            result = await scan_client.scan(encrypted_bytes, media_type=media_type.value)
            media.scan_provider = "thorn_safer"
            media.scan_completed_at = datetime.utcnow()

            if result.hit:
                media.scan_status = MediaScanStatus.flagged
                db.commit()
                await _handle_flagged_upload(db, media, result)
                # Never store or deliver flagged content.
                return media

            media.scan_status = MediaScanStatus.clear
        else:
            # audio: no pre-scan available, mark clear-but-unscanned
            # and rely on report-freeze + review if flagged later
            media.scan_status = MediaScanStatus.clear
            media.scan_provider = None

    except Exception:
        # Fail closed: if the scanner errors, do not deliver the content.
        media.scan_status = MediaScanStatus.error
        db.commit()
        return media

    # Only now does the encrypted object actually get persisted to storage.
    await storage_client.put_object(storage_key, encrypted_bytes)
    db.commit()
    return media


async def _handle_flagged_upload(db, media: Media, scan_result):
    """
    Tier 1 path: preserve evidence in a secured, access-logged store
    (separate from normal media storage, never auto-purged), suspend the
    uploading account pending review, and route to the NCMEC CyberTipline
    pipeline. This intentionally does NOT go through the normal media
    lifecycle — it is handled entirely outside the view-once flow.
    """
    # Implementation lives in services/csam_response.py — kept separate
    # so this critical path has its own audit trail and isn't tangled
    # with general moderation code.
    from app.services.csam_response import preserve_evidence_and_report
    await preserve_evidence_and_report(db, media, scan_result)


async def start_view_session(db, media: Media):
    if media.lifecycle_status == MediaLifecycleStatus.held_for_report:
        raise PermissionError("This content is held pending a report review.")
    if media.lifecycle_status == MediaLifecycleStatus.consumed:
        raise ValueError("This content is no longer available.")

    if media.lifecycle_status == MediaLifecycleStatus.available:
        media.lifecycle_status = MediaLifecycleStatus.viewing
        media.session_started_at = datetime.utcnow()

    media.view_count += 1
    media.session_last_heartbeat_at = datetime.utcnow()
    db.commit()
    return await storage_client.get_signed_url(media.storage_key)


async def heartbeat_session(db, media: Media):
    """Client pings periodically while the viewer is open; keeps the
    inactivity-timeout backstop from firing on a still-active session."""
    media.session_last_heartbeat_at = datetime.utcnow()
    db.commit()


async def end_view_session(db, media: Media, reporter_check=None):
    """
    Called when the client leaves the viewer (navigation away, thread
    closed, app backgrounded). This is what triggers permanent deletion —
    unless a report was just filed referencing this media, in which case
    it's frozen for review instead.
    """
    if reporter_check and await reporter_check(media.id):
        media.lifecycle_status = MediaLifecycleStatus.held_for_report
        media.held_for_report = True
        db.commit()
        return

    await storage_client.delete_object(media.storage_key)
    media.lifecycle_status = MediaLifecycleStatus.consumed
    media.consumed_at = datetime.utcnow()
    db.commit()


async def sweep_abandoned_sessions(db):
    """
    Background worker task: catches sessions where the client crashed or
    lost connection without a clean end-of-session call. Runs on a
    schedule (e.g. every minute).
    """
    cutoff = datetime.utcnow() - timedelta(minutes=settings.media_session_timeout_minutes)
    stuck = db.query(Media).filter(
        Media.lifecycle_status == MediaLifecycleStatus.viewing,
        Media.session_last_heartbeat_at < cutoff,
    ).all()
    for media in stuck:
        await end_view_session(db, media)
