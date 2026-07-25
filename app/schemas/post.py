from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    body_text: str = Field(..., min_length=1, max_length=2000)
    intent_tags: list[str] = Field(default_factory=list)
    location_label: Optional[str] = Field(None, max_length=120)


class PostOut(BaseModel):
    id: uuid.UUID
    body_text: str
    intent_tags: list[str]
    location_label: Optional[str]
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True
