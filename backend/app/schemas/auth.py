"""Schemas shared by authentication endpoints."""
from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str


# --- Forgot password (no email/OTP — the ID card itself is the proof) --------
# Backs POST /auth/student/forgot-password/verify and
# POST /auth/student/forgot-password/reset. See
# app/api/v1/endpoints/auth.py — both reuse the existing registration
# verification engine (app.ai.pipeline.analyze_registration_photo) rather
# than a second identity-verification system.


class PasswordResetVerifyResponse(BaseModel):
    """Response for POST /auth/student/forgot-password/verify. `reset_token`
    is short-lived and scoped to exactly one purpose — see
    app.core.security.TokenRole and app.api.deps.get_password_reset_student
    — never a normal login/session token."""

    reset_token: str


class PasswordResetCompleteRequest(BaseModel):
    """Body for POST /auth/student/forgot-password/reset, authenticated by
    the `reset_token` from the verify step (as a Bearer token), not by any
    field in this body."""

    new_password: str = Field(..., min_length=8, max_length=128)
