"""unified student roster

Revision ID: 0014_unified_student_roster
Revises: 0013_student_master
Create Date: 2026-08-10 00:00:00.000000

Milestone: Unified Student Roster. Collapses the two-table
`Student` / `StudentMaster` concept down to one: `students` becomes the
single source of truth for the college roster, and `student_master` is
dropped. There is no more student self-registration — every account is
now administrator-provisioned (Excel import, see
`app/services/excel_import_service.py`).

What this migration does, in order:

  1. Adds the new roster columns to `students`: `batch` (nullable,
     free text), `password_changed` (NOT NULL, default false),
     `is_active` (NOT NULL, default true), `updated_at` (NOT NULL,
     default now()).
  2. Resets **every** existing student's password to the new
     administrator-issued default (`excel_import_service.
     DEFAULT_STUDENT_PASSWORD`, hashed) and `password_changed = false`.
     This is a deliberate, spec'd decision for this migration specifically
     (not the ongoing behavior of a re-import, which never touches an
     existing password — see `excel_import_service.py`'s docstring): every
     account that existed under the old self-registration system is being
     converted, in one stroke, into an administrator-provisioned account,
     and administrator-provisioned accounts always start on the default
     password with the mandatory Change Password screen armed. A student
     who forgets the new default is told to contact their administrator
     (`POST /admin/students/{id}/reset-to-default`), the same as any other
     roster account going forward.
  3. Upserts `student_master` rows into `students`, matched by PRN
     (case-insensitive): a `student_master` row with no matching `Student`
     becomes a brand-new `Student` row (this is exactly the "every
     imported student is already a SnapAttend account" rule, applied
     retroactively to rosters imported before this migration existed); a
     `student_master` row that *does* match an existing `Student` backfills
     that student's `full_name` and `panel_id` from the roster data (the
     roster is the source of truth for those fields, same as a live Excel
     re-import) without touching its `id`, `prn`, or (freshly reset)
     password.
  4. Drops `student_master` and its indexes.
  5. Drops the now-unused registration-audit columns from `students`:
     `verified_prn`, `verified_name`, `id_image_path`, `verified_at`
     (all artifacts of the removed registration flow), and `division`
     (superseded by the new `batch` field — see this milestone's field-set
     decision).

Preserves, untouched: `teachers`, `courses`, `panels`, `panel_course`,
`teacher_course`, `attendance_sessions`, `attendance`,
`attendance_device_lock`, `admins`. `attendance.student_id` /
`attendance_device_lock.student_id` both already carry
`ondelete="CASCADE"` at the DB level (unchanged by this migration) — no
`Student` row is deleted here, only updated or inserted, so no attendance
history is at risk.

Downgrade note: this migration's password reset (step 2) is one-way — a
downgrade cannot recover the pre-migration password hashes, since they are
overwritten, not stored anywhere else. `downgrade()` below restores the
schema shape (recreates `student_master` as an empty table, restores the
dropped `students` columns) but cannot and does not attempt to restore
data that step 2/3 already merged or overwrote; that data-level
consolidation is the entire, intentional point of this migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision: str = "0014_unified_student_roster"
down_revision: Union[str, None] = "0013_student_master"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors excel_import_service.DEFAULT_STUDENT_PASSWORD — deliberately not
# imported directly (migrations in this project are kept import-self-
# contained, per every prior revision here that hashes a password; see
# 0007_admin_system).
_DEFAULT_STUDENT_PASSWORD = "test@123"  # noqa: S105 - the milestone's specified default, hashed before storage


def upgrade() -> None:
    bind = op.get_bind()
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # --- 1. New roster columns -------------------------------------------------
    op.add_column("students", sa.Column("batch", sa.String(length=50), nullable=True))
    op.add_column(
        "students", sa.Column("password_changed", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("students", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column(
        "students",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    students = sa.table(
        "students",
        sa.column("id", sa.Integer),
        sa.column("prn", sa.String),
        sa.column("full_name", sa.String),
        sa.column("batch", sa.String),
        sa.column("panel_id", sa.Integer),
        sa.column("password_hash", sa.String),
        sa.column("password_changed", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    student_master = sa.table(
        "student_master",
        sa.column("prn", sa.String),
        sa.column("full_name", sa.String),
        sa.column("panel_id", sa.Integer),
    )

    # --- 2. Reset every existing student to the new default password -----------
    default_password_hash = pwd_context.hash(_DEFAULT_STUDENT_PASSWORD)
    bind.execute(
        students.update().values(password_hash=default_password_hash, password_changed=False)
    )

    # --- 3. Upsert student_master rows into students, matched by PRN -----------
    existing_prns: dict[str, int] = {
        (row.prn or "").strip().lower(): row.id
        for row in bind.execute(sa.select(students.c.id, students.c.prn))
    }

    new_rows: list[dict] = []
    for row in bind.execute(sa.select(student_master.c.prn, student_master.c.full_name, student_master.c.panel_id)):
        prn = (row.prn or "").strip()
        if not prn:
            continue
        key = prn.lower()
        matched_id = existing_prns.get(key)
        if matched_id is not None:
            bind.execute(
                students.update()
                .where(students.c.id == matched_id)
                .values(full_name=row.full_name, panel_id=row.panel_id)
            )
        else:
            new_rows.append(
                {
                    "prn": prn,
                    "full_name": row.full_name,
                    "panel_id": row.panel_id,
                    "batch": None,
                    "password_hash": default_password_hash,
                    "password_changed": False,
                    "is_active": True,
                }
            )
            # Guard against two student_master rows sharing a PRN
            # (shouldn't happen — prn is unique there too — but keeps this
            # loop's own in-memory view consistent either way).
            existing_prns[key] = -1

    if new_rows:
        bind.execute(sa.insert(students), new_rows)

    # --- 4. Drop student_master -------------------------------------------------
    op.drop_index(op.f("ix_student_master_panel_id"), table_name="student_master")
    op.drop_index(op.f("ix_student_master_prn"), table_name="student_master")
    op.drop_table("student_master")

    # --- 5. Drop now-unused columns ---------------------------------------------
    op.drop_column("students", "verified_prn")
    op.drop_column("students", "verified_name")
    op.drop_column("students", "id_image_path")
    op.drop_column("students", "verified_at")
    op.drop_column("students", "division")


def downgrade() -> None:
    # Restore the pre-migration columns (schema-only — see this module's
    # docstring's "Downgrade note" for why the data itself can't come back).
    op.add_column("students", sa.Column("division", sa.String(length=50), nullable=True))
    op.add_column("students", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("students", sa.Column("id_image_path", sa.String(length=255), nullable=True))
    op.add_column("students", sa.Column("verified_name", sa.String(length=150), nullable=True))
    op.add_column("students", sa.Column("verified_prn", sa.String(length=50), nullable=True))

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

    op.drop_column("students", "updated_at")
    op.drop_column("students", "is_active")
    op.drop_column("students", "password_changed")
    op.drop_column("students", "batch")
