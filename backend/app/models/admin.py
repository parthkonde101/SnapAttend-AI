"""Administrator ORM model (Milestone 7A — Administrator System).

Deliberately its own table, not a flag on `Teacher` — an Administrator is
explicitly NOT a teacher (unrestricted access across every teacher's
courses/sessions, versus a teacher who only ever sees their own), so
giving it a separate identity/table keeps that distinction structural
rather than something every query has to remember to check. Mirrors
`Teacher`'s shape closely (login id + name + bcrypt hash + created_at) so
the authentication code paths stay symmetric — see
`app/core/security.py`'s `TokenRole` and `app/api/deps.py`'s
`get_current_admin`.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Admin(Base):
    __tablename__ = "admins"

    # No `index=True` here — the primary key constraint already provides
    # Postgres's own implicit unique index on `id`; a second explicit index
    # would be redundant, and (per the lesson from migration
    # 0006_attendance_device_lock's fixed duplicate-index bug) is exactly
    # the pattern that risks a future `alembic revision --autogenerate`
    # trying to recreate it. The migration that actually creates this table
    # (0007_admin_system) matches: it indexes only `login_id`.
    id: Mapped[int] = mapped_column(primary_key=True)
    login_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Admin id={self.id} login_id={self.login_id!r}>"
