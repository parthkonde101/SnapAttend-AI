"""Password hashing and JWT token utilities."""
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenRole = Literal["student", "teacher", "password_reset"]
"""`password_reset` is deliberately a distinct role, not just a normal
student token issued early — see app.api.deps.get_password_reset_student.
A token minted after ID-card verification during the forgot-password flow
must only ever be usable for "set a new password", never as a substitute
student session token (which would let a bare ID-card photo, without ever
proving knowledge of the current password, grant full account access)."""


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: TokenRole, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token for a student or teacher subject."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode: dict[str, Any] = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
