import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class BannedContact(Base):
    """
    Permanent record of banned phone/email hashes. Survives even if the
    originating user account is deleted. Checked at signup to block
    re-registration by a previously banned user (Tier 1/2 violations).
    """
    __tablename__ = "banned_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_ref_hash = Column(String(128), unique=True, nullable=False, index=True)
    reason = Column(Text, nullable=False)  # short internal note, e.g. "Tier 1 - CSAM"
    banned_at = Column(DateTime, default=datetime.utcnow)
    banned_by_mod_id = Column(UUID(as_uuid=True), nullable=True)
