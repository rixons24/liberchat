import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.report import ReportReason


class ReportCreate(BaseModel):
    reported_user_id: uuid.UUID
    reason: ReportReason
    detail_text: Optional[str] = None

    post_id: Optional[uuid.UUID] = None
    thread_id: Optional[uuid.UUID] = None
    reported_message_ids: Optional[list[uuid.UUID]] = None

    # Reporter's client submits its own decrypted view of the relevant
    # messages, since the server never holds plaintext for E2EE content.
    thread_snapshot: Optional[dict] = None
