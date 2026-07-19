"""panel-course compatibility

Revision ID: 0012_panel_courses
Revises: 0011_course_archive
Create Date: 2026-08-03 00:00:01.000000

Milestone 8B, Part 4/9 — Panel Management + Teacher Session course->panel
filtering. Purely additive:
  * new `panel_courses` many-to-many join table (panel_id, course_id)

No existing table's existing columns are altered or dropped. No backfill
is performed — Milestone 8A shipped panels and courses with no notion of
"which courses does this panel study," so there is no historical data to
migrate; every panel starts with zero assigned courses and an
administrator assigns them going forward via the panel's Courses tab. This
is the same "no data to invent, so don't invent any" posture migration
0009 took for `students.panel_id`.

`ondelete="CASCADE"` on both FKs (mirrors `teacher_courses`, migration
0008): deleting a Panel or a Course should remove its own compatibility
rows, not leave orphaned join rows behind — this never touches
`attendance_sessions` history, which references Panel/Course independently
via its own nullable `SET NULL` foreign keys (migration 0010).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_panel_courses"
down_revision: Union[str, None] = "0011_course_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panel_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("panel_id", sa.Integer(), sa.ForeignKey("panels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("panel_id", "course_id", name="uq_panel_course"),
    )
    op.create_index(op.f("ix_panel_courses_panel_id"), "panel_courses", ["panel_id"])
    op.create_index(op.f("ix_panel_courses_course_id"), "panel_courses", ["course_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_panel_courses_course_id"), table_name="panel_courses")
    op.drop_index(op.f("ix_panel_courses_panel_id"), table_name="panel_courses")
    op.drop_table("panel_courses")
