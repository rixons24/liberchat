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


class PrekeyBundle(Base):
    """
    Public key material a user publishes so others can initiate an
    encrypted session with them (X3DH). Only public keys are ever stored
    server-side — private keys never leave the originating device.
    """
    __tablename__ = "prekey_bundles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    identity_key_public = Column(String, nullable=False)
    signed_prekey_public = Column(String, nullable=False)
    signed_prekey_signature = Column(String, nullable=False)
    one_time_prekey_public = Column(String, nullable=True)  # consumed on use, replenished by client
    registration_id = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


async def publish_prekey_bundle(db, user_id: uuid.UUID, bundle: dict):
    """Client calls this on signup/key rotation to publish fresh public key material."""
    row = PrekeyBundle(
        user_id=user_id,
        identity_key_public=bundle["identity_key_public"],
        signed_prekey_public=bundle["signed_prekey_public"],
        signed_prekey_signature=bundle["signed_prekey_signature"],
        one_time_prekey_public=bundle.get("one_time_prekey_public"),
        registration_id=bundle["registration_id"],
    )
    db.add(row)
    db.commit()
    return row


async def fetch_prekey_bundle(db, user_id: uuid.UUID):
    """
    Called by the initiating client when starting a new DM thread — fetches
    the other party's public bundle to run the X3DH handshake locally.
    One-time prekey is consumed (deleted) once fetched, per protocol.
    """
    row = (
        db.query(PrekeyBundle)
        .filter_by(user_id=user_id)
        .order_by(PrekeyBundle.created_at.desc())
        .first()
    )
    if row is None:
        raise ValueError("No prekey bundle available for this user.")

    result = {
        "identity_key_public": row.identity_key_public,
        "signed_prekey_public": row.signed_prekey_public,
        "signed_prekey_signature": row.signed_prekey_signature,
        "one_time_prekey_public": row.one_time_prekey_public,
        "registration_id": row.registration_id,
    }

    if row.one_time_prekey_public:
        row.one_time_prekey_public = None  # consumed, client must replenish supply later
        db.commit()

    return result
