import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class UserStatus(str, enum.Enum):
    active = "active"
    banned = "banned"
    shadowbanned = "shadowbanned"
    suspended_dm = "suspended_dm"  # DM privileges paused pending mod review


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Public-facing identity — never the real name
    handle = Column(String(32), unique=True, nullable=False, index=True)

    # contact_ref is a salted hash of phone/email, used ONLY for abuse-ban
    # enforcement (block re-registration). Never exposed to other users,
    # never used to display identity anywhere in the product.
    contact_ref_hash = Column(String(128), unique=True, nullable=False, index=True)

    # Self-attested, not verified — Reddit-style model
    dob_attested = Column(DateTime, nullable=False)
    age_gate_accepted_at = Column(DateTime, nullable=False)
    nsfw_opt_in = Column(Boolean, default=False)

    # Phone verification (SMS OTP) — current baseline signal for Tanzania
    # since carrier-based Age Verification API (GSMA Open Gateway/CAMARA)
    # is not yet available from Tanzanian MNOs as of this build.
    phone_verified_at = Column(DateTime, nullable=True)

    # Reserved for when/if a Tanzanian carrier joins the GSMA Open Gateway
    # age-verification network. Left nullable/unused until then — wiring
    # it in later should not require a schema change.
    carrier_age_check_result = Column(String(16), nullable=True)  # "pass" | "fail" | None
    carrier_age_check_at = Column(DateTime, nullable=True)

    email_verified_at = Column(DateTime, nullable=True)

    status = Column(Enum(UserStatus), default=UserStatus.active, nullable=False)
    report_count = Column(Integer, default=0)
    strikes = Column(Integer, default=0)

    password_hash = Column(String(256), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
