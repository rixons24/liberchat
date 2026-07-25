from datetime import datetime, timedelta

from jose import jwt, JWTError

from app.config import settings


def create_access_token(user_id: str, token_type: str = "user") -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "typ": token_type}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, expected_type: str = "user") -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # Strict type check — a leaked/guessed regular-user token must never
        # be usable as an admin token, and vice versa.
        if payload.get("typ") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None
