"""course normalization

Revision ID: 0008_courses
Revises: 0007_admin_system
Create Date: 2026-07-20 00:00:00.000000

Milestone 8A, Part 3 — Course Normalization. Purely additive:
  * new `courses` table (id, course_code, course_name, created_at)
  * new `teacher_courses` many-to-many join table (teacher_id, course_id)
  * data backfill: every distinct, non-empty `teachers.course` value in the
    database becomes exactly one `Course` row, and every teacher who had
    that value gets a matching `TeacherCourse` row linking them to it.

No existing table's existing columns are altered or dropped.
`teachers.course` itself is left completely untouched by this
migration — still present, still populated exactly as it was — it is only
*read* here to seed the new tables. See `app/models/teacher.py`'s updated
docstring for why it now says "deprecated" rather than being removed:
dropping it would be a destructive, non-additive change with no
compensating benefit, and several existing admin read-paths (e.g. a
historical session that predates `AttendanceSession.course_id`, added in
migration 0010) still fall back to it for display purposes.

`course_code` has no historical equivalent (the old free-text field was
never a structured code), so this migration invents one per distinct
course name: the alphabetic characters of the name, uppercased, truncated
to 12 characters, with a numeric suffix appended only if that collides
with a code already generated in this same run. It is intentionally
`nullable=True` at the schema level — invented, not authoritative — so an
administrator can correct it later via the Manage Courses screen without
a second migration. Every course created going forward through the admin
API is required to supply a real one (see `CourseCreateRequest`).
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_courses"
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_courses_course_code"), "courses", ["course_code"], unique=True)

    op.create_table(
        "teacher_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "teacher_id", sa.Integer(), sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("teacher_id", "course_id", name="uq_teacher_course"),
    )
    op.create_index(op.f("ix_teacher_courses_teacher_id"), "teacher_courses", ["teacher_id"])
    op.create_index(op.f("ix_teacher_courses_course_id"), "teacher_courses", ["course_id"])

    # --- Data backfill: Teacher.course (free text) -> Course + TeacherCourse ---
    # NOTE: these are `sa.Table` objects bound to a throwaway local
    # `MetaData()`, not the lighter-weight `sa.table()`/`sa.column()`
    # shadow-table idiom used elsewhere for read-only queries. That's
    # deliberate: `sa.table()` never registers a primary key, so
    # `result.inserted_primary_key` below would always come back empty
    # (confirmed dialect-agnostic — reproduces identically on SQLite and
    # is a documented SQLAlchemy Core behavior, not a backend quirk) and
    # this backfill would crash on the very first course insert. Marking
    # `id` with `primary_key=True` on a real `sa.Table` is what makes
    # `inserted_primary_key` resolve correctly (via cursor.lastrowid /
    # RETURNING, depending on dialect).
    bind = op.get_bind()
    _md = sa.MetaData()
    teachers_table = sa.Table(
        "teachers",
        _md,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course", sa.String),
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
            result = bind.execute(
                courses_table.insert().values(course_code=code, course_name=name)
            )
            course_id = result.inserted_primary_key[0]
            course_id_by_name[name] = course_id

        bind.execute(teacher_courses_table.insert().values(teacher_id=teacher_id, course_id=course_id))


def downgrade() -> None:
    op.drop_index(op.f("ix_teacher_courses_course_id"), table_name="teacher_courses")
    op.drop_index(op.f("ix_teacher_courses_teacher_id"), table_name="teacher_courses")
    op.drop_table("teacher_courses")

    op.drop_index(op.f("ix_courses_course_code"), table_name="courses")
    op.drop_table("courses")
