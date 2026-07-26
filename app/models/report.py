import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.database import Base


class ReportReason(str, enum.Enum):
    underage = "underage"                    # Tier 1 - jumps queue, auto-freeze, NCMEC path
    threat_or_violence = "threat_or_violence"  # Tier 1
    non_consensual = "non_consensual"          # Tier 1
    solicitation = "solicitation"               # Tier 2
    harassment = "harassment"                   # Tier 2
    unsolicited_explicit_media = "unsolicited_explicit_media"  # Tier 2
    scam = "scam"                                # Tier 3
    spam = "spam"                                # Tier 3
    other = "other"


TIER_1_REASONS = {ReportReason.underage, ReportReason.threat_or_violence, ReportReason.non_consensual}
TIER_2_REASONS = {ReportReason.solicitation, ReportReason.harassment, ReportReason.unsolicited_explicit_media}


class ReportStatus(str, enum.Enum):
    open = "open"
    under_review = "under_review"
    resolved = "resolved"


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reported_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("dm_threads.id"), nullable=True)

    reason = Column(Enum(ReportReason), nullable=False)
    detail_text = Column(Text, nullable=True)

    status = Column(Enum(ReportStatus), default=ReportStatus.open, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Mandatory before a moderator can close a Tier 1/2 case — audit trail.
    mod_action = Column(String(64), nullable=True)   # e.g. "removed_and_banned"
    mod_note = Column(Text, nullable=True)
    mod_id = Column(UUID(as_uuid=True), nullable=True)


class MessageReport(Base):
    """
    Links a report to specific DM content and freezes a snapshot of it —
    bypassing the normal disappearing-message/media lifecycle so evidence
    survives long enough for a moderator to actually review it.
    """
    __tablename__ = "message_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=False)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("dm_threads.id"), nullable=False)

    reported_message_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)

    # Frozen copy of relevant thread content at time of report. For E2EE
    # text this means capturing what the reporting user's client can see
    # (their own decrypted view) since the server never holds plaintext —
    # the reporter's app submits the decrypted snapshot as part of filing
    # the report. For media, this sets held_for_report on the Media rows
    # directly (see media_pipeline.end_view_session).
    thread_snapshot = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Block(Base):
    __tablename__ = "blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blocker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    blocked_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ThreadRead(Base):
    """
    Tracks when each participant last read a thread. A DMThread is shared
    between two users, so read-state can't live on the thread itself -
    each user has their own row here, updated whenever they open/view
    that thread. Used to compute unread indicators in the inbox list.
    """
    __tablename__ = "thread_reads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("dm_threads.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    last_read_at = Column(DateTime, default=datetime.utcnow)
