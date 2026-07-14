"""registration verification fields

Revision ID: 0003_registration_verification
Revises: 0002_attendance_session_engine
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_registration_verification"
down_revision: Union[str, None] = "0002_attendance_session_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("verified_prn", sa.String(length=50), nullable=True))
    op.add_column("students", sa.Column("verified_name", sa.String(length=150), nullable=True))
    op.add_column("students", sa.Column("id_image_path", sa.String(length=255), nullable=True))
    op.add_column("students", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "verified_at")
    op.drop_column("students", "id_image_path")
    op.drop_column("students", "verified_name")
    op.drop_column("students", "verified_prn")
