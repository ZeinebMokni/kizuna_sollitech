from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    locale: str = Field(default="fr", pattern=r"^[a-z]{2}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    expires_at: datetime


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    locale: str
    roles: list[str]
