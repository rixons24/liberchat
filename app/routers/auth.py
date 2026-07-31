from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_redis
from app.core.security import create_access_token
from app.core.rate_limit import limiter
from app.config import settings
from app.schemas.user import SignupStart, OtpVerify, SignupComplete, LoginRequest, LoginResponse
from app.services import auth_service
from app.models.user import User, UserStatus

router = APIRouter()


@router.post("/signup/start")
@limiter.limit("3/minute")
async def signup_start(request: Request, payload: SignupStart, db: Session = Depends(get_db), redis=Depends(get_redis)):
    contact_hash = auth_service.hash_contact_ref(payload.phone_number)

    if auth_service.is_banned_contact_ref(db, contact_hash):
        # Deliberately vague error — don't reveal ban-list logic to the caller
        raise HTTPException(status_code=400, detail="Unable to complete signup.")

    if db.query(User).filter_by(contact_ref_hash=contact_hash).first():
        raise HTTPException(status_code=400, detail="An account already exists for this number.")

    if db.query(User).filter_by(handle=payload.handle).first():
        raise HTTPException(status_code=400, detail="Handle already taken.")

    await auth_service.send_otp(redis, payload.phone_number)

    # Stash pending signup data in Redis keyed by phone, consumed on OTP verify
    await redis.set(
        f"pending_signup:{payload.phone_number}",
        payload.model_dump_json(),
        ex=600,
    )
    return {"message": "OTP sent."}


@router.post("/signup/verify", response_model=SignupComplete)
@limiter.limit("10/minute")
async def signup_verify(request: Request, payload: OtpVerify, db: Session = Depends(get_db), redis=Depends(get_redis)):
    ok = await auth_service.verify_otp(redis, payload.phone_number, payload.otp_code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    pending_raw = await redis.get(f"pending_signup:{payload.phone_number}")
    if pending_raw is None:
        raise HTTPException(status_code=400, detail="Signup session expired, please start again.")

    pending = SignupStart.model_validate_json(pending_raw)
    contact_hash = auth_service.hash_contact_ref(pending.phone_number)

    user = User(
        handle=pending.handle,
        contact_ref_hash=contact_hash,
        dob_attested=datetime.combine(pending.dob, datetime.min.time()),
        age_gate_accepted_at=datetime.utcnow(),
        phone_verified_at=datetime.utcnow(),
        password_hash=auth_service.hash_password(pending.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    await redis.delete(f"pending_signup:{pending.phone_number}")

    token = create_access_token(str(user.id))
    return SignupComplete(user_id=str(user.id), handle=user.handle, phone_verified=True, access_token=token)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    contact_hash = auth_service.hash_contact_ref(payload.phone_number)
    user = db.query(User).filter_by(contact_ref_hash=contact_hash).first()

    # Deliberately identical error for "no such user" and "wrong password"
    # so login can't be used to enumerate registered phone numbers.
    if not user or not auth_service.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone number or password.")

    if user.status == UserStatus.banned:
        raise HTTPException(status_code=403, detail="This account has been banned.")

    user.last_seen_at = datetime.utcnow()
    db.commit()

    token = create_access_token(str(user.id))
    return LoginResponse(user_id=str(user.id), handle=user.handle, access_token=token)


@router.get("/debug/otp/{phone_number}")
@limiter.limit("10/minute")
async def debug_get_otp(request: Request, phone_number: str, redis=Depends(get_redis)):
    """
    TEMPORARY, TESTING ONLY. Returns the current OTP for a phone number so
    signup can be tested before a real SMS provider is wired up.

    Gated behind DEBUG_OTP_ENDPOINT_ENABLED, which defaults to false/unset.
    This must never be enabled in a real deployment — retrieving OTPs
    without owning the phone number entirely defeats phone verification
    as a security measure. Delete this endpoint once SMS_PROVIDER_API_KEY
    is set and confirmed working.
    """
    if not settings.debug_otp_endpoint_enabled:
        raise HTTPException(status_code=404, detail="Not found.")

    otp = await redis.get(f"otp:{phone_number}")
    if otp is None:
        raise HTTPException(status_code=404, detail="No pending OTP for this number.")
    return {"phone_number": phone_number, "otp_code": otp.decode() if isinstance(otp, bytes) else otp}
