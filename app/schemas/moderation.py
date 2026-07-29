from typing import Literal

from pydantic import BaseModel, Field


class ModerationAction(BaseModel):
    action: Literal[
        "dismiss",
        "remove_content",
        "remove_and_strike",
        "remove_and_ban",
        "remove_ban_and_report_ncmec",
    ]
    note: str = Field(..., min_length=1, description="Required audit note explaining the decision.")


class UserBanRequest(BaseModel):
    note: str = Field(..., min_length=1, description="Required audit note explaining the ban.")
