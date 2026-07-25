import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MediaType(str, enum.Enum):
    image = "image"
    video = "video"
    audio = "audio"


class MediaScanStatus(str, enum.Enum):
    pending = "pending"       # queued for moderation scan, not yet viewable
    clear = "clear"           # passed scan, viewable
    flagged = "flagged"       # failed scan, held for review, never delivered to recipient
    error = "error"           # scan failed to run — fail closed, treat like flagged


class MediaLifecycleStatus(str, enum.Enum):
    available = "available"   # uploaded, scanned clear, not yet opened
    viewing = "viewing"       # an active viewer session is open
    consumed = "consumed"     # session ended, content permanently deleted
    held_for_report = "held_for_report"  # frozen — report filed before/during viewing


class Media(Base):
    __tablename__ = "media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NOTE: intentionally NOT a ForeignKey constraint. Message.media_id
    # already provides the enforced link (Message -> Media). Adding a
    # second enforced FK in the opposite direction (Media -> Message)
    # creates a circular dependency that Postgres can't resolve at table
    # creation time. This column stays as a plain indexed UUID purely
    # for convenience lookups.
    message_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    type = Column(Enum(MediaType), nullable=False)

    # Encrypted object storage key (R2/S3). The object itself is encrypted
    # client-side before upload (E2EE) — server stores ciphertext bytes and
    # never holds a usable decryption key.
    storage_key = Column(String(256), nullable=False)
    duration_seconds = Column(Integer, nullable=True)  # cap enforced at upload for video/audio

    scan_status = Column(Enum(MediaScanStatus), default=MediaScanStatus.pending, nullable=False)
    scan_provider = Column(String(32), nullable=True)  # e.g. "thorn_safer", "photodna"
    scan_completed_at = Column(DateTime, nullable=True)

    lifecycle_status = Column(Enum(MediaLifecycleStatus), default=MediaLifecycleStatus.available, nullable=False)

    # Incremented on every replay/re-scrub within a single open viewer
    # session. NOT incremented across sessions, because media is deleted
    # the moment a session ends (Option A — locked in).
    view_count = Column(Integer, default=0)

    session_started_at = Column(DateTime, nullable=True)
    session_last_heartbeat_at = Column(DateTime, nullable=True)  # backstop for crashed/abandoned sessions

    uploaded_at = Column(DateTime, default=datetime.utcnow)
    consumed_at = Column(DateTime, nullable=True)  # when actually deleted

    held_for_report = Column(Boolean, default=False)
