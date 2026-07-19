"""panel system

Revision ID: 0009_panels
Revises: 0008_courses
Create Date: 2026-07-20 00:00:01.000000

Milestone 8A, Part 2 — Panel System. Purely additive:
  * new `panels` table (id, name, created_at)
  * `students.panel_id` — nullable foreign key to `panels.id`

No existing table's existing columns are altered, no existing row's
existing data is touched or lost. `students.panel_id` is nullable at the
database level on purpose: an existing student row cannot be retroactively
assigned a real panel by a migration (there is no correct value to invent),
so every pre-existing student simply starts with `panel_id = NULL` — "no
data loss," not "silently invent data." Panel selection is required at the
*application* layer for every *new* registration going forward (see
`StudentRegister.panel_id` in `app/schemas/student.py`), not enforced with
a `NOT NULL` constraint here.

`ondelete="SET NULL"` (matches the FK on the model, `app/models/student.py`)
so deleting a Panel via the admin CRUD never cascades into deleting
students — it only clears their panel assignment back to "unassigned."
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_panels"
down_revision: Union[str, None] = "0008_courses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_panels_name"), "panels", ["name"], unique=True)

    op.add_column("students", sa.Column("panel_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_students_panel_id"), "students", ["panel_id"])
    op.create_foreign_key(
        "fk_students_panel_id_panels", "students", "panels", ["panel_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_students_panel_id_panels", "students", type_="foreignkey")
    op.drop_index(op.f("ix_students_panel_id"), table_name="students")
    op.drop_column("students", "panel_id")

    op.drop_index(op.f("ix_panels_name"), table_name="panels")
    op.drop_table("panels")
