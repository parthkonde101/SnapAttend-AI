"""administrator system

Revision ID: 0007_admin_system
Revises: 0006_attendance_device_lock
Create Date: 2026-07-16 00:00:00.000000

Milestone 7A. Purely additive:
  * new `admins` table, seeded with the first administrator account
    (login id "ADMIN", bcrypt-hashed password, per the milestone spec —
    never stored in plaintext)
  * `teachers.course` — nullable, backfills existing rows to NULL
  * `students.division` — nullable, backfills existing rows to NULL

No existing table's existing columns are altered, no existing row's
existing data is touched. `students.division` and `teachers.course` are
read only by the new admin management screens; nothing in registration,
login, or attendance verification depends on them.

The seed admin password is hashed here with the exact same algorithm
(`bcrypt` via passlib's `CryptContext`) `app/core/security.hash_password`
uses for every other account in this system — deliberately not importing
that module directly (migrations in this project are kept import-self-
contained, per every prior revision here), but configured identically
(`schemes=["bcrypt"], deprecated="auto"`) so the resulting hash verifies
correctly against `verify_password` at login time.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision: str = "0007_admin_system"
down_revision: Union[str, None] = "0006_attendance_device_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_ADMIN_LOGIN_ID = "ADMIN"
_SEED_ADMIN_FULL_NAME = "System Administrator"
_SEED_ADMIN_PASSWORD = "990912"  # noqa: S105 - the milestone's specified initial credential, hashed before storage


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("login_id", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_admins_login_id"), "admins", ["login_id"], unique=True)

    op.add_column("teachers", sa.Column("course", sa.String(length=150), nullable=True))
    op.add_column("students", sa.Column("division", sa.String(length=50), nullable=True))

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admins_table = sa.table(
        "admins",
        sa.column("login_id", sa.String),
        sa.column("full_name", sa.String),
        sa.column("password_hash", sa.String),
    )
    op.bulk_insert(
        admins_table,
        [
            {
                "login_id": _SEED_ADMIN_LOGIN_ID,
                "full_name": _SEED_ADMIN_FULL_NAME,
                "password_hash": pwd_context.hash(_SEED_ADMIN_PASSWORD),
            }
        ],
    )


def downgrade() -> None:
    op.drop_column("students", "division")
    op.drop_column("teachers", "course")

    op.drop_index(op.f("ix_admins_login_id"), table_name="admins")
    op.drop_table("admins")
