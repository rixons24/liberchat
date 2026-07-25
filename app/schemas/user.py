from datetime import date
from pydantic import BaseModel, Field, field_validator


class SignupStart(BaseModel):
    """Step 1: user provides phone + DOB + accepts safety interstitial."""
    phone_number: str = Field(..., description="E.164 format, e.g. +2557XXXXXXXX")
    dob: date
    age_gate_accepted: bool
    handle: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=10)

    @field_validator("age_gate_accepted")
    @classmethod
    def must_accept_gate(cls, v):
        if not v:
            raise ValueError("Safety notice must be accepted to continue.")
        return v

    @field_validator("dob")
    @classmethod
    def must_be_18(cls, v: date):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("You must be 18 or older to use LiberChat.")
        return v


class OtpVerify(BaseModel):
    phone_number: str
    otp_code: str = Field(..., min_length=4, max_length=8)


class SignupComplete(BaseModel):
    user_id: str
    handle: str
    phone_verified: bool
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    phone_number: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    handle: str
    access_token: str
    token_type: str = "bearer"
