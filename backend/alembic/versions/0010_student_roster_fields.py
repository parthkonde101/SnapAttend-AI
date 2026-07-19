"""student roster fields: panel, roll number, batch, forced password change

Revision ID: 0010_student_roster_fields
Revises: 0009_session_course_panel
Create Date: 2026-07-18 00:00:02.000000

"Extending the attendance system" spec, Part 3/4 — Student Import System +
Student Password Reset. Purely additive:
  * `students.panel_id` — nullable FK to `panels.id`, `ondelete="SET NULL"`
  * `students.roll_number` — nullable, panel-local roster identifier
  * `students.batch` — nullable
  * `students.password_changed` — NOT NULL, backfilled to `true` for every
    existing row
  * `students.is_active` — NOT NULL, backfilled to `true` for every existing row
  * `students.updated_at` — NOT NULL, backfilled to `now()` for every existing row

No existing table's existing columns are altered or dropped, and no
existing student's password/account is touched.

`password_changed` defaults to `true` for pre-existing rows deliberately —
those students self-registered and already chose their own password (the
self-registration flow predates this milestone and is untouched), so they
have nothing to be forced to change. Only a *new* Excel-imported row (or an
administrator's "Reset Password" action, both application-layer writes
after this migration) ever sets this `false`, which is what actually
triggers the mandatory change-password screen — see
`app/services/excel_import_service.py` and
`AdminStudentService.reset_to_default_password`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_student_roster_fields"
down_revision: Union[str, None] = "0009_session_course_panel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("panel_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_students_panel_id"), "students", ["panel_id"])
    op.create_foreign_key(
        "fk_students_panel_id_panels", "students", "panels", ["panel_id"], ["id"], ondelete="SET NULL"
    )

    op.add_column("students", sa.Column("roll_number", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_students_roll_number"), "students", ["roll_number"])

    op.add_column("students", sa.Column("batch", sa.String(length=50), nullable=True))

    op.add_column(
        "students", sa.Column("password_changed", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("students", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column(
        "students",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("students", "updated_at")
    op.drop_column("students", "is_active")
    op.drop_column("students", "password_changed")
    op.drop_column("students", "batch")
    op.drop_index(op.f("ix_students_roll_number"), table_name="students")
    op.drop_column("students", "roll_number")
    op.drop_constraint("fk_students_panel_id_panels", "students", type_="foreignkey")
    op.drop_index(op.f("ix_students_panel_id"), table_name="students")
    op.drop_column("students", "panel_id")
