"""course archive flag

Revision ID: 0011_course_archive
Revises: 0010_session_course_panel
Create Date: 2026-08-03 00:00:00.000000

Milestone 8B, Part 2 — Course Management. Purely additive:
  * `courses.is_archived` — NOT NULL boolean, server_default false.

A server_default (rather than an application-only default) means every
existing course row is backfilled to `is_archived = false` by the database
itself as part of this single migration, so the column can be NOT NULL from
day one with no separate backfill step and no risk of a NULL slipping
through. Archiving a course never deletes it or anything that references
it (TeacherCourse, PanelCourse, AttendanceSession.course_id all keep
working exactly as before) — it only removes it from admin/teacher
*picker* UIs going forward. See `app/models/course.py`'s updated docstring.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_course_archive"
down_revision: Union[str, None] = "0010_session_course_panel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("courses", "is_archived")
