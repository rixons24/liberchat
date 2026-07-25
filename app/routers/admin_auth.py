from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.deps import get_db
from app.core.security import create_access_token
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
