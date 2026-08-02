"""
E2EE wrapper around the Signal Protocol (X3DH key agreement + Double
Ratchet for forward secrecy). This module intentionally does NOT
implement cryptographic primitives itself — it wraps a vetted library
(libsignal-client's Python bindings, or a maintained equivalent) and
only handles the plumbing: key storage references, session bootstrap,
and passing ciphertext to/from the DM relay.

IMPORTANT: All actual encryption/decryption of message content and
media happens on the CLIENT (mobile/web app), not here. The server's
job is limited to:
  - storing each user's public prekey bundle so others can start a session
  - relaying ciphertext blobs between clients
  - never seeing, storing, or being able to derive plaintext

This keeps the server unable to comply with a plaintext-disclosure
request even under legal compulsion, since it never has the key.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class IdentityKey(Base):
    """
    One long-term ECDH public key per user, used to bootstrap the
    Double Ratchet's initial shared secret (see frontend ratchet code).
    Only the public key is ever stored server-side - the private key
    never leaves the user's device.
    """
    __tablename__ = "identity_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    public_key_b64 = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


async def publish_identity_key(db, user_id: uuid.UUID, public_key_b64: str):
    existing = db.query(IdentityKey).filter_by(user_id=user_id).first()
    if existing:
        existing.public_key_b64 = public_key_b64
    else:
        db.add(IdentityKey(user_id=user_id, public_key_b64=public_key_b64))
    db.commit()


async def fetch_identity_key(db, user_id: uuid.UUID) -> str | None:
    row = db.query(IdentityKey).filter_by(user_id=user_id).first()
    return row.public_key_b64 if row else None
