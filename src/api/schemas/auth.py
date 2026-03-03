"""Pydantic schemas for auth endpoints."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
