from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.deps import get_db
from app.core.security import create_access_token
from app.config import settings
from app.services import auth_service
from app.models.admin import AdminUser

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    admin_id: str
    username: str
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter_by(username=payload.username).first()

    # Identical error for "no such admin" and "wrong password" — don't let
    # this endpoint be used to enumerate valid admin usernames.
    if not admin or not auth_service.verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Admin account disabled.")

    admin.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token(str(admin.id), token_type="admin")
    return AdminLoginResponse(admin_id=str(admin.id), username=admin.username, access_token=token)


@router.get("/bootstrap")
async def bootstrap_admin(username: str, password: str, db: Session = Depends(get_db)):
    """
    TEMPORARY, FOR INITIAL SETUP ONLY. Creates the first admin account
    over HTTP, for platforms (like Render's free tier) with no Shell/
    One-Off Jobs access to run scripts/create_admin.py normally.

    Double-gated for safety:
      1. Requires BOOTSTRAP_ADMIN_ENABLED=true explicitly set - defaults
         to off (404), same as the debug OTP endpoint.
      2. Self-disables the moment ANY admin account exists, regardless
         of the env var - so even if left enabled, it can't be reused
         to create additional unauthorized admins later.

    Set BOOTSTRAP_ADMIN_ENABLED back to false (or remove it) once used.
    """
    if not settings.bootstrap_admin_enabled:
        raise HTTPException(status_code=404, detail="Not found.")

    if db.query(AdminUser).count() > 0:
        raise HTTPException(status_code=403, detail="An admin account already exists — this endpoint only works once.")

    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters.")

    admin = AdminUser(username=username, password_hash=auth_service.hash_password(password))
    db.add(admin)
    db.commit()
    return {"message": f"Admin account '{username}' created. Now set BOOTSTRAP_ADMIN_ENABLED back to false."}
