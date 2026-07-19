"""courses, panels, and their many-to-many joins

Revision ID: 0008_courses_panels
Revises: 0007_admin_system
Create Date: 2026-07-18 00:00:00.000000

"Extending the attendance system" spec, Parts 1-2 — Teacher<->Course
many-to-many and Academic Panels. Purely additive:
  * new `courses` table (id, course_code, course_name, is_archived, created_at)
  * new `panels` table (id, name, academic_year, created_at)
  * new `teacher_courses` many-to-many join table (teacher_id, course_id)
  * new `panel_courses` many-to-many join table (panel_id, course_id)
  * data backfill: every distinct, non-empty `teachers.course` value
    becomes exactly one `Course` row, and every teacher who had that value
    gets a matching `TeacherCourse` row linking them to it — "migrate
    existing data wherever possible."

No existing table's existing columns are altered or dropped.
`teachers.course` itself is left completely untouched — still present,
still populated exactly as it was — it is only *read* here to seed the new
tables, and is now considered deprecated in favor of `TeacherCourse` (see
`app/models/teacher.py`). Dropping it would be a destructive, non-additive
change with no compensating benefit.

`course_code` has no historical equivalent (the old free-text field was
never a structured code), so this migration invents one per distinct
course name: the alphanumeric characters of the name, uppercased,
truncated to 12 characters, with a numeric suffix appended only if that
collides with a code already generated in this same run. It is
intentionally nullable at the schema level — invented, not authoritative —
so an administrator can correct it later. Every course created going
forward through the admin API is required to supply a real one.

Every panel starts with zero assigned courses and zero students (a
student's panel assignment comes from the Excel import, added in migration
0010) — there is no historical "which panel was a student in" data to
invent, so nothing is backfilled here beyond the course/teacher link
above, per "no data loss, don't invent data."
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_courses_panels"
down_revision: Union[str, None] = "0007_admin_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _generate_course_code(course_name: str, used_codes: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9]", "", course_name).upper()[:12] or "COURSE"
    candidate = base
    suffix = 2
    while candidate in used_codes:
        candidate = f"{base[:10]}{suffix}"
        suffix += 1
    used_codes.add(candidate)
    return candidate


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_code", sa.String(length=50), nullable=True),
        sa.Column("course_name", sa.String(length=150), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_courses_course_code"), "courses", ["course_code"], unique=True)

    op.create_table(
        "panels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_panels_name"), "panels", ["name"], unique=True)

    op.create_table(
        "teacher_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("teacher_id", "course_id", name="uq_teacher_course"),
    )
    op.create_index(op.f("ix_teacher_courses_teacher_id"), "teacher_courses", ["teacher_id"])
    op.create_index(op.f("ix_teacher_courses_course_id"), "teacher_courses", ["course_id"])

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

    # --- Data backfill: Teacher.course (free text) -> Course + TeacherCourse ---
    # Real `sa.Table` objects (not the lighter `sa.table()`/`sa.column()`
    # shadow idiom) so `result.inserted_primary_key` resolves correctly —
    # see migration 0008_courses (archived) for the full rationale; this is
    # the identical, previously-verified pattern.
    bind = op.get_bind()
    _md = sa.MetaData()
    teachers_table = sa.Table(
        "teachers", _md, sa.Column("id", sa.Integer, primary_key=True), sa.Column("course", sa.String)
    )
    courses_table = sa.Table(
        "courses",
        _md,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_code", sa.String),
        sa.Column("course_name", sa.String),
    )
    teacher_courses_table = sa.Table(
        "teacher_courses",
        _md,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("teacher_id", sa.Integer),
        sa.Column("course_id", sa.Integer),
    )

    rows = list(bind.execute(sa.select(teachers_table.c.id, teachers_table.c.course)))

    used_codes: set[str] = set()
    course_id_by_name: dict[str, int] = {}

    for teacher_id, course_name in rows:
        if not course_name or not course_name.strip():
            continue
        name = course_name.strip()

        course_id = course_id_by_name.get(name)
        if course_id is None:
            code = _generate_course_code(name, used_codes)
            result = bind.execute(courses_table.insert().values(course_code=code, course_name=name))
            course_id = result.inserted_primary_key[0]
            course_id_by_name[name] = course_id

        bind.execute(teacher_courses_table.insert().values(teacher_id=teacher_id, course_id=course_id))


def downgrade() -> None:
    op.drop_index(op.f("ix_panel_courses_course_id"), table_name="panel_courses")
    op.drop_index(op.f("ix_panel_courses_panel_id"), table_name="panel_courses")
    op.drop_table("panel_courses")

    op.drop_index(op.f("ix_teacher_courses_course_id"), table_name="teacher_courses")
    op.drop_index(op.f("ix_teacher_courses_teacher_id"), table_name="teacher_courses")
    op.drop_table("teacher_courses")

    op.drop_index(op.f("ix_panels_name"), table_name="panels")
    op.drop_table("panels")

    op.drop_index(op.f("ix_courses_course_code"), table_name="courses")
    op.drop_table("courses")
