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
    Generates an OTP, stores it in Redis with TTL, and sends via Twilio SMS.
    Falls back to logging only (no real SMS) if Twilio credentials aren't
    configured - keeps local dev working without requiring real creds.
    """
    code = generate_otp()
    key = f"otp:{phone_number}"
    await redis.set(key, code, ex=OTP_TTL_MINUTES * 60)

    if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            to=phone_number,
            from_=settings.twilio_phone_number,
            body=f"Your LiberChat verification code is: {code}",
        )
    else:
        print(f"[DEV ONLY - no Twilio configured] OTP for {phone_number}: {code}")


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
