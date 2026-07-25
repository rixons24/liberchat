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
from app.schemas.dm import ThreadStartRequest, ThreadOut, MessageOut

router = APIRouter()

# In-memory connection registry. For multi-instance deployment, replace
# with a Redis pub/sub channel per thread instead of a local dict.
active_connections: dict[str, WebSocket] = {}


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
        raise HTTPException(status_code=400, detail="Can't start a thread with your own post.")

    # Reuse an existing thread between these two users tied to this post,
    # rather than creating duplicates on every "Respond" tap.
    existing = db.query(DMThread).filter(
        DMThread.post_id == post.id,
        ((DMThread.user_a_id == current_user.id) & (DMThread.user_b_id == other_user_id))
        | ((DMThread.user_a_id == other_user_id) & (DMThread.user_b_id == current_user.id)),
    ).first()
    if existing:
        return existing

    thread = DMThread(post_id=post.id, user_a_id=current_user.id, user_b_id=other_user_id)
    db.add(thread)
    db.commit()
    db.refresh(thread)
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
