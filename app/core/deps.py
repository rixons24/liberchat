import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User, UserStatus
from app.models.admin import AdminUser

_redis_client = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    user_id = decode_access_token(token, expected_type="user")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    if user.status == UserStatus.banned:
        raise HTTPException(status_code=403, detail="Account banned.")
    return user


def get_current_moderator(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    Entirely separate auth path from get_current_user — a regular
    consumer account, however trusted, can never satisfy this dependency.
    Requires a token issued by /admin/login against the admin_users table.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    admin_id = decode_access_token(token, expected_type="admin")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token.")
    admin = db.query(AdminUser).get(admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return admin


async def get_current_user_ws(websocket, db: Session):
    """
    WebSocket auth: token passed as a query param (?token=...) since
    WS handshakes can't carry custom Authorization headers from all
    clients reliably. Swap for a subprotocol-based token if preferred.
    """
    token = websocket.query_params.get("token")
    if not token:
        return None
    user_id = decode_access_token(token, expected_type="user")
    if not user_id:
        return None
    user = db.query(User).get(user_id)
    if not user or user.status == UserStatus.banned:
        return None
    return user
