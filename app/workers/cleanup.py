"""
Scheduled background jobs. Run via Celery beat or a simple asyncio loop
(arq works well if you want to stay lightweight rather than pulling in
full Celery). Each job is idempotent and safe to run on overlapping
schedules.
"""

import asyncio
from datetime import datetime

from app.database import SessionLocal
from app.models.post import Post, PostStatus
from app.models.media import Media, MediaLifecycleStatus
from app.services import media_pipeline


async def expire_posts():
    """Marks posts past their expires_at as expired. Runs every few minutes."""
    db = SessionLocal()
    try:
        stale = (
            db.query(Post)
            .filter(Post.status == PostStatus.active, Post.expires_at < datetime.utcnow())
            .all()
        )
        for post in stale:
            post.status = PostStatus.expired
        db.commit()
    finally:
        db.close()


async def sweep_abandoned_media_sessions():
    """Backstop for crashed/abandoned viewer sessions. Runs every minute."""
    db = SessionLocal()
    try:
        await media_pipeline.sweep_abandoned_sessions(db)
    finally:
        db.close()


async def purge_orphaned_flagged_media():
    """
    Safety check: anything sitting in `flagged` scan status for more than
    a short window should have already been routed into the evidence
    pipeline (csam_response). This job just alerts if something is stuck
    in limbo — it does NOT auto-delete flagged content, since that content
    must never be purged before compliance review.
    """
    db = SessionLocal()
    try:
        from app.models.media import MediaScanStatus
        stuck = (
            db.query(Media)
            .filter(Media.scan_status == MediaScanStatus.flagged)
            .all()
        )
        for m in stuck:
            # TODO: alert compliance if a flagged item hasn't been picked
            # up by the evidence pipeline within an expected window.
            pass
    finally:
        db.close()


async def run_forever():
    while True:
        await expire_posts()
        await sweep_abandoned_media_sessions()
        await purge_orphaned_flagged_media()
        await asyncio.sleep(60)


async def start_background_workers():
    asyncio.create_task(run_forever())
