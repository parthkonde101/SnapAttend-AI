"""attendance session course + panel

Revision ID: 0010_session_course_panel
Revises: 0009_panels
Create Date: 2026-07-20 00:00:02.000000

Milestone 8A — ties an attendance session to the specific `Course` and
`Panel` a teacher selected when starting it (Part 2 / Part 3). Purely
additive:
  * `attendance_sessions.course_id` — nullable FK to `courses.id`
  * `attendance_sessions.panel_id` — nullable FK to `panels.id`

Both nullable at the database level: every session that already exists
predates course/panel selection entirely, and there is no correct value to
backfill (a legacy session's teacher may since have been assigned several
courses, and no panel concept existed at all when it was created) — so
existing rows simply get `NULL` in both new columns, per "no data loss."
Going forward, the teacher "Start Attendance" flow requires choosing both
(enforced in `AttendanceSessionService.start_session`), but that is an
application-layer rule, not a `NOT NULL` constraint here, for the same
reason `students.panel_id` (migration 0009) isn't one either.

`ondelete="SET NULL"` on both — deleting a Course or Panel via the admin
CRUD never cascades into deleting attendance history, it only clears that
historical session's course/panel reference.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_session_course_panel"
down_revision: Union[str, None] = "0009_panels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attendance_sessions", sa.Column("course_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_attendance_sessions_course_id"), "attendance_sessions", ["course_id"])
    op.create_foreign_key(
        "fk_attendance_sessions_course_id_courses",
        "attendance_sessions",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("attendance_sessions", sa.Column("panel_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_attendance_sessions_panel_id"), "attendance_sessions", ["panel_id"])
    op.create_foreign_key(
        "fk_attendance_sessions_panel_id_panels",
        "attendance_sessions",
        "panels",
        ["panel_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_attendance_sessions_panel_id_panels", "attendance_sessions", type_="foreignkey")
    op.drop_index(op.f("ix_attendance_sessions_panel_id"), table_name="attendance_sessions")
    op.drop_column("attendance_sessions", "panel_id")

    op.drop_constraint("fk_attendance_sessions_course_id_courses", "attendance_sessions", type_="foreignkey")
    op.drop_index(op.f("ix_attendance_sessions_course_id"), table_name="attendance_sessions")
    op.drop_column("attendance_sessions", "course_id")
