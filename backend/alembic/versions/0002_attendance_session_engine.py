"""attendance session engine

Revision ID: 0002_attendance_session_engine
Revises: 0001_initial_schema
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_attendance_session_engine"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New fixed-duration field driving the 90 second session engine.
    op.add_column(
        "attendance_sessions",
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="90"),
    )

    # Session codes are now short (3 character) and reused over time, so a
    # global uniqueness constraint on the code itself no longer holds.
    # Uniqueness of the *active* session is enforced separately below.
    op.drop_index(op.f("ix_attendance_sessions_session_code"), table_name="attendance_sessions")
    op.create_index(
        op.f("ix_attendance_sessions_session_code"), "attendance_sessions", ["session_code"], unique=False
    )

    # Guarantee at most one active session system-wide at the database level.
    op.create_index(
        "uq_attendance_sessions_single_active",
        "attendance_sessions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_sessions_single_active", table_name="attendance_sessions")

    op.drop_index(op.f("ix_attendance_sessions_session_code"), table_name="attendance_sessions")
    op.create_index(
        op.f("ix_attendance_sessions_session_code"), "attendance_sessions", ["session_code"], unique=True
    )

    op.drop_column("attendance_sessions", "duration_seconds")
