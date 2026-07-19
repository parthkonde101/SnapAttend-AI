"""student master database

Revision ID: 0013_student_master
Revises: 0012_panel_courses
Create Date: 2026-08-03 00:00:02.000000

Milestone 8B, Part 5 — Student Master Database. Purely additive:
  * new `student_master` table (id, prn, full_name, official_email,
    department, semester, panel_id, academic_status, created_at)

This is a brand-new, empty table — no existing data is migrated into it,
because none exists: `Student` (the authentication table) has never stored
department/semester/official_email, so there is nothing to backfill from.
An administrator populates this table going forward via Excel import (Part
6) or an admin never at all for a given student, in which case that
student's registration falls back to "PRN not found in the academic
database" per Part 7's manual-entry branch — an intentional, spec'd
outcome, not a migration concern.

`prn` carries its own unique index (mirrors `students.prn`) — this is the
join key back to `Student`, by value, not by foreign key (see
`app/models/student_master.py`'s docstring for why). `panel_id` reuses the
exact nullable, `ondelete="SET NULL"` pattern `students.panel_id` already
established in migration 0009: deleting a Panel un-assigns every
StudentMaster row that pointed at it rather than deleting roster data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_student_master"
down_revision: Union[str, None] = "0012_panel_courses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_master",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prn", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("official_email", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("semester", sa.String(length=20), nullable=True),
        sa.Column("panel_id", sa.Integer(), sa.ForeignKey("panels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_student_master_prn"), "student_master", ["prn"], unique=True)
    op.create_index(op.f("ix_student_master_panel_id"), "student_master", ["panel_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_student_master_panel_id"), table_name="student_master")
    op.drop_index(op.f("ix_student_master_prn"), table_name="student_master")
    op.drop_table("student_master")
