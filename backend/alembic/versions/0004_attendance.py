"""attendance verification engine v1

Revision ID: 0004_attendance
Revises: 0003_registration_verification
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Kept short deliberately: PostgreSQL's alembic_version.version_num column
# is VARCHAR(32) (Alembic's own default), and the original id chosen here
# ("0004_attendance_verification_engine", 36 characters) exceeded it,
# breaking `alembic upgrade` with StringDataRightTruncation. This id
# ("0004_attendance", 16 characters) safely fits, matching the existing
# short-id convention already used by every other revision in this project
# (e.g. "0001_initial_schema", "0002_attendance_session_engine").
revision: str = "0004_attendance"
down_revision: Union[str, None] = "0003_registration_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The single A-Z0-9 character shown on the teacher's projected session
    # display and verified against each student's capture. server_default
    # only exists to backfill any pre-existing rows; every new session gets
    # a freshly generated marker (see app/services/attendance_session_service.py).
    op.add_column(
        "attendance_sessions",
        sa.Column("marker", sa.String(length=1), nullable=False, server_default="A"),
    )

    op.add_column(
        "attendance",
        sa.Column("verification_source", sa.String(length=20), nullable=False, server_default="ocr"),
    )
    op.add_column(
        "attendance",
        sa.Column("marker", sa.String(length=1), nullable=False, server_default="A"),
    )
    op.add_column(
        "attendance",
        sa.Column("verification_duration_ms", sa.Float(), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column("image_reference", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendance", "image_reference")
    op.drop_column("attendance", "verification_duration_ms")
    op.drop_column("attendance", "marker")
    op.drop_column("attendance", "verification_source")

    op.drop_column("attendance_sessions", "marker")
