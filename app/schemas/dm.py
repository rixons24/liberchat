import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ThreadStartRequest(BaseModel):
    post_id: uuid.UUID


class ThreadOut(BaseModel):
    id: uuid.UUID
    post_id: Optional[uuid.UUID]
    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    ciphertext: Optional[str]
    media_id: Optional[uuid.UUID]
    media_info: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadSummaryOut(BaseModel):
    id: uuid.UUID
    other_user_handle: str
    last_message_at: datetime
    unread: bool
    reported: bool
