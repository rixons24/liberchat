import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DMThread(Base):
    __tablename__ = "dm_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Nullable because a thread should outlive the post it originated
    # from if the poster deletes the post once they've found someone.
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=True)

    user_a_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user_b_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)

    # Set true if either participant has blocked the other — hides the
    # thread from both without deleting message history (needed if a
    # report is later filed referencing this thread).
    blocked = Column(Boolean, default=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("dm_threads.id"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # E2EE: server only ever stores/relays ciphertext. Encryption/decryption
    # happens client-side via the Signal Protocol session established
    # between the two participants (see services/encryption.py for the
    # key-exchange handshake, X3DH + Double Ratchet).
    ciphertext = Column(Text, nullable=True)  # null if this message is media-only

    media_id = Column(UUID(as_uuid=True), ForeignKey("media.id"), nullable=True)

    # Set once a report references this message — freezes it from
    # whatever deletion/expiry logic would otherwise apply, so moderators
    # have evidence to review. Checked by the cleanup worker before purge.
    held_for_report = Column(Boolean, default=False)
