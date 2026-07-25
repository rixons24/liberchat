import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

OTP_TTL_MINUTES = 10


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_contact_ref(value: str) -> str:
    """
    Salted hash of phone number or email, used ONLY to:
      - detect/block re-registration by a previously banned user
      - deduplicate accounts
    Never reversed, never displayed, never linked to a visible identity.
    """
    return hmac.new(
        settings.contact_ref_salt.encode(),
        value.strip().lower().encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_otp(redis, phone_number: str) -> None:
    """
    Generates an OTP, stores it in Redis with TTL, and sends via SMS provider.
    Swap the send step for Twilio Verify / Africa's Talking / local SMS
    gateway as appropriate for Tanzania.
    """
    code = generate_otp()
    key = f"otp:{phone_number}"
    await redis.set(key, code, ex=OTP_TTL_MINUTES * 60)

    # TODO: wire to actual SMS provider, e.g.:
    # await sms_client.send(to=phone_number, body=f"Your LiberChat code: {code}")


async def verify_otp(redis, phone_number: str, code: str) -> bool:
    key = f"otp:{phone_number}"
    stored = await redis.get(key)
    if stored is None:
        return False
    if secrets.compare_digest(stored.decode(), code):
        await redis.delete(key)
        return True
    return False


def is_banned_contact_ref(db, contact_ref_hash: str) -> bool:
    """
    Checked at signup before account creation — permanently banned
    contact_ref hashes stay in a separate table forever, even after
    the original account is deleted, so a banned user can't just
    re-register with the same number/email.
    """
    from app.models.banned_contact import BannedContact  # local import avoids cycle
    return db.query(BannedContact).filter_by(contact_ref_hash=contact_ref_hash).first() is not None
