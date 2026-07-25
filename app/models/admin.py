import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AdminUser(Base):
    """
    Deliberately separate from the consumer `users` table. Admin/moderator
    access should never ride on the same login surface as regular
    accounts — no phone OTP, no self-registration. Admin accounts are
    created out-of-band (see scripts/create_admin.py) by someone who
    already has server access, not through any public endpoint.
    """
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)

    is_active = Column(Boolean, default=True)
    # Reserved for later if you want tiers (e.g. senior mod can NCMEC-report,
    # junior mod cannot) — unused for now, everyone with an active admin
    # account has full moderator access.
    role = Column(String(32), default="moderator")

    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
