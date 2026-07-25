import uuid
import enum
from datetime import datetime, timedelta

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.database import Base
from app.config import settings


class PostStatus(str, enum.Enum):
    active = "active"
    deleted_by_author = "deleted_by_author"
    expired = "expired"
    removed_by_mod = "removed_by_mod"


class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Never exposed client-side to other users — only used server-side
    # to route DMs back to the poster.
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    body_text = Column(Text, nullable=False)
    intent_tags = Column(ARRAY(String), default=list)

    # Free-text / neighborhood-level only. Never coordinates. Set by the
    # poster themselves — the platform never collects or infers location.
    location_label = Column(String(120), nullable=True)

    status = Column(Enum(PostStatus), default=PostStatus.active, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=settings.post_default_expiry_hours),
    )
    deleted_at = Column(DateTime, nullable=True)
