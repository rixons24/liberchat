"""
Relays ciphertext between two participants in a DM thread. The server's
role here is intentionally dumb: authenticate the connection, verify the
sender is a participant in the thread, persist the ciphertext blob, and
push it to the recipient if they're online (or let them fetch on next
connect if not). No plaintext ever passes through this layer.
"""

import uuid
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user_ws, get_current_user
from app.models.dm import DMThread, Message
from app.models.user import User, UserStatus
from app.models.post import Post
from app.models.report import ThreadRead
from app.schemas.dm import ThreadStartRequest, ThreadOut, MessageOut, ThreadSummaryOut

router = APIRouter()

# In-memory connection registry. For multi-instance deployment, replace
# with a Redis pub/sub channel per thread instead of a local dict.
active_connections: dict[str, WebSocket] = {}


def _mark_read(db: Session, thread_id, user_id):
    read = db.query(ThreadRead).filter_by(thread_id=thread_id, user_id=user_id).first()
    if read:
        read.last_read_at = datetime.utcnow()
    else:
        db.add(ThreadRead(thread_id=thread_id, user_id=user_id, last_read_at=datetime.utcnow()))
    db.commit()


@router.get("/threads", response_model=list[ThreadSummaryOut])
async def list_threads(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Every thread the current user is part of, regardless of whether they
    started it or are the post author being responded to. This is the
    only way a post author can find and open conversations replying to
    their own posts - opening their own post directly can't resolve to
    a single thread, since multiple people may have responded to it.
    """
    threads = db.query(DMThread).filter(
        (DMThread.user_a_id == current_user.id) | (DMThread.user_b_id == current_user.id)
    ).order_by(DMThread.last_message_at.desc()).all()

    result = []
    for t in threads:
        other_id = t.user_b_id if t.user_a_id == current_user.id else t.user_a_id
        other_user = db.query(User).get(other_id)

        last_message = db.query(Message).filter_by(thread_id=t.id).order_by(Message.created_at.desc()).first()
        read = db.query(ThreadRead).filter_by(thread_id=t.id, user_id=current_user.id).first()

        unread = False
        if last_message and last_message.sender_id != current_user.id:
            if not read or last_message.created_at > read.last_read_at:
                unread = True

        result.append(ThreadSummaryOut(
            id=t.id,
            other_user_handle=other_user.handle if other_user else "Unknown",
            last_message_at=t.last_message_at,
            last_message_from_me=bool(last_message and last_message.sender_id == current_user.id),
            unread=unread,
            reported=t.blocked,
        ))
    return result


@router.post("/thread/{thread_id}/read")
async def mark_thread_read(thread_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    thread = db.query(DMThread).get(thread_id)
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=404, detail="Thread not found.")
    _mark_read(db, thread.id, current_user.id)
    return {"ok": True}


@router.post("/identity-key")
async def publish_identity_key(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.encryption import publish_identity_key as _publish
    await _publish(db, current_user.id, payload["public_key_b64"])
    return {"message": "Identity key published."}


@router.get("/identity-key/{user_id}")
async def get_identity_key(
    user_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    from app.services.encryption import fetch_identity_key as _fetch
    key = await _fetch(db, user_id)
    if key is None:
        raise HTTPException(status_code=404, detail="No identity key published for this user yet.")
    return {"public_key_b64": key}


@router.post("/thread/start", response_model=ThreadOut)
async def start_thread(
    payload: ThreadStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(payload.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    other_user_id = post.author_id
    if other_user_id == current_user.id:
        # The post's own author tapped their own post - there's no single
        # thread to resolve to (multiple people may have responded).
        # Point them at their inbox instead of erroring.
        raise HTTPException(
            status_code=409,
            detail="This is your own post. Check your Messages tab to see responses.",
        )

    # Reuse an existing thread between these two users tied to this post,
    # rather than creating duplicates on every "Respond" tap.
    existing = db.query(DMThread).filter(
        DMThread.post_id == post.id,
        ((DMThread.user_a_id == current_user.id) & (DMThread.user_b_id == other_user_id))
        | ((DMThread.user_a_id == other_user_id) & (DMThread.user_b_id == current_user.id)),
    ).first()
    if existing:
        _mark_read(db, existing.id, current_user.id)
        return existing

    thread = DMThread(post_id=post.id, user_a_id=current_user.id, user_b_id=other_user_id)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    _mark_read(db, thread.id, current_user.id)
    return thread


@router.get("/thread/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch thread metadata directly by id - used when opening an existing
    thread from the inbox, bypassing thread/start entirely."""
    thread = db.query(DMThread).get(thread_id)
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=404, detail="Thread not found.")
    _mark_read(db, thread.id, current_user.id)
    return thread


@router.get("/thread/{thread_id}/messages", response_model=list[MessageOut])
async def get_thread_messages(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = db.query(DMThread).get(thread_id)
    if not thread or current_user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=404, detail="Thread not found.")

    _mark_read(db, thread.id, current_user.id)

    from app.models.media import Media
    messages = db.query(Message).filter_by(thread_id=thread.id).order_by(Message.created_at.asc()).all()

    result = []
    for m in messages:
        media_info = None
        if m.media_id:
            media_row = db.query(Media).get(m.media_id)
            if media_row:
                media_info = {"type": media_row.type, "nsfw": media_row.nsfw, "consumed": media_row.lifecycle_status == "consumed"}
        result.append(MessageOut(
            id=m.id, sender_id=m.sender_id, ciphertext=m.ciphertext,
            media_id=m.media_id, media_info=media_info, created_at=m.created_at,
        ))
    return result


@router.websocket("/ws/{thread_id}")
async def dm_socket(websocket: WebSocket, thread_id: str, db: Session = Depends(get_db)):
    user = await get_current_user_ws(websocket, db)
    if user is None:
        await websocket.close(code=4401)
        return

    thread = db.query(DMThread).get(thread_id)
    if thread is None or user.id not in (thread.user_a_id, thread.user_b_id):
        await websocket.close(code=4403)
        return

    if thread.blocked:
        await websocket.close(code=4403)
        return

    if user.status == UserStatus.suspended_dm:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    conn_key = f"{thread_id}:{user.id}"
    active_connections[conn_key] = websocket

    other_user_id = thread.user_b_id if user.id == thread.user_a_id else thread.user_a_id

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            # Expected payload: { "ciphertext": "...", "media_id": null | "<uuid>" }

            other_status = db.query(User.status).filter(User.id == other_user_id).scalar()
            if other_status == UserStatus.banned:
                await websocket.send_json({"error": "Recipient is unavailable."})
                continue

            message = Message(
                thread_id=thread.id,
                sender_id=user.id,
                ciphertext=payload.get("ciphertext"),
                media_id=payload.get("media_id"),
            )
            db.add(message)
            thread.last_message_at = datetime.utcnow()
            db.commit()
            db.refresh(message)

            recipient_key = f"{thread_id}:{other_user_id}"
            recipient_ws = active_connections.get(recipient_key)

            media_info = None
            if message.media_id:
                from app.models.media import Media
                media_row = db.query(Media).get(message.media_id)
                if media_row:
                    media_info = {"type": media_row.type, "nsfw": media_row.nsfw}

            if recipient_ws is not None:
                await recipient_ws.send_json({
                    "message_id": str(message.id),
                    "sender_id": str(user.id),
                    "ciphertext": message.ciphertext,
                    "media_id": str(message.media_id) if message.media_id else None,
                    "media_info": media_info,
                    "created_at": message.created_at.isoformat(),
                })
            # If recipient isn't connected, the message is already persisted
            # (as ciphertext) and will be delivered when they next connect
            # and fetch thread history via the REST endpoint.

    except WebSocketDisconnect:
        active_connections.pop(conn_key, None)
