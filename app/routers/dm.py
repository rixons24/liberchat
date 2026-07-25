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

from app.core.deps import get_db, get_current_user_ws
from app.models.dm import DMThread, Message
from app.models.user import User, UserStatus

router = APIRouter()

# In-memory connection registry. For multi-instance deployment, replace
# with a Redis pub/sub channel per thread instead of a local dict.
active_connections: dict[str, WebSocket] = {}


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
            if recipient_ws is not None:
                await recipient_ws.send_json({
                    "message_id": str(message.id),
                    "sender_id": str(user.id),
                    "ciphertext": message.ciphertext,
                    "media_id": str(message.media_id) if message.media_id else None,
                    "created_at": message.created_at.isoformat(),
                })
            # If recipient isn't connected, the message is already persisted
            # (as ciphertext) and will be delivered when they next connect
            # and fetch thread history via the REST endpoint.

    except WebSocketDisconnect:
        active_connections.pop(conn_key, None)
