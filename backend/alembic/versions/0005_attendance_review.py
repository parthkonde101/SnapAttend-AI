"""attendance verification philosophy refinement + teacher review

Revision ID: 0005_attendance_review
Revises: 0004_attendance
Create Date: 2026-07-15 00:00:00.000000

Purely additive: every new column has a server_default so existing rows
(all of which are AI-verified "present" attempts from before this
migration) backfill to `status='present'`, `display_detected=false`,
`display_confidence=0.0`, `marker_verification_mode='exact_match'`,
`is_teacher_override=false` — i.e. exactly what they already were, just
now expressed in the new columns instead of being implicit. Nothing here
drops or renames an existing column, and no existing row is touched beyond
that backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_attendance_review"
down_revision: Union[str, None] = "0004_attendance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attendance",
        sa.Column("status", sa.String(length=10), nullable=False, server_default="present"),
    )
    op.add_column(
        "attendance",
        sa.Column("marker_detected_character", sa.String(length=1), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column("marker_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "attendance",
        sa.Column("display_detected", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "attendance",
        sa.Column("display_confidence", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "attendance",
        sa.Column("marker_verification_mode", sa.String(length=20), nullable=False, server_default="exact_match"),
    )
    op.add_column(
        "attendance",
        sa.Column("is_teacher_override", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "attendance",
        sa.Column("overridden_by_teacher_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendance_overridden_by_teacher_id",
        "attendance",
        "teachers",
        ["overridden_by_teacher_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "attendance",
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendance", "overridden_at")
    op.drop_constraint("fk_attendance_overridden_by_teacher_id", "attendance", type_="foreignkey")
    op.drop_column("attendance", "overridden_by_teacher_id")
    op.drop_column("attendance", "is_teacher_override")
    op.drop_column("attendance", "marker_verification_mode")
    op.drop_column("attendance", "display_confidence")
    op.drop_column("attendance", "display_detected")
    op.drop_column("attendance", "marker_confidence")
    op.drop_column("attendance", "marker_detected_character")
    op.drop_column("attendance", "status")
