"""temporary session-scoped device lock

Revision ID: 0006_attendance_device_lock
Revises: 0005_attendance_review
Create Date: 2026-07-15 00:00:00.000000

Adds `attendance_device_locks`: a brand-new, purely additive table. No
existing table or column is touched. Rows exist only for the lifetime of
one active attendance session — see
`app/services/device_lock_service.py` and `AttendanceSessionService`'s
cleanup calls, which delete every row for a session the moment it ends.

Migration-correctness note (fixed after an initial `alembic upgrade head`
failure): the `id` column must NOT be declared with `index=True` inside
`op.create_table(...)`. Alembic's `create_table` implementation creates the
table and then iterates `table.indexes`, issuing a `CREATE INDEX` for every
index registered on the table object — and `index=True` on a `Column`
auto-registers exactly such an index (named `ix_<table>_<column>` by
SQLAlchemy's default naming convention). A *second*, explicit
`op.create_index("ix_attendance_device_locks_id", ...)` call right after
`create_table` therefore tried to create a same-named index a second time,
which Postgres rejects as `DuplicateTable` (index names live in the same
relation namespace as tables). Since Postgres DDL is transactional, the
whole migration rolled back — including the `CREATE TABLE` itself — which
is why `\d attendance_device_locks` showed no table at all afterwards even
though the failure happened on the *second* statement.

The fix is to drop the redundant index entirely rather than de-duplicate
it: a primary key column already has its own implicit unique B-tree index
in Postgres (created by the `PRIMARY KEY` constraint itself), so a second,
non-unique index on that same single column adds no query benefit — it's
pure redundant overhead. `session_id` is unaffected: it was never marked
`index=True` inline, so its single explicit `op.create_index(...)` call
below was always correct and remains untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_attendance_device_lock"
down_revision: Union[str, None] = "0005_attendance_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_device_locks",
        # No `index=True` here — see this migration's module docstring.
        # The primary key constraint already provides Postgres's implicit
        # unique index on `id`; a second explicit index would be both
        # redundant and (if named identically) a duplicate-relation error.
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["attendance_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "device_id", name="uq_device_lock_session_device"),
    )
    # The one real lookup index this table needs: DeviceLockService queries
    # are always scoped by session_id (see `_get_lock` / `clear_locks_for_session`).
    op.create_index(
        op.f("ix_attendance_device_locks_session_id"), "attendance_device_locks", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_device_locks_session_id"), table_name="attendance_device_locks")
    op.drop_table("attendance_device_locks")
