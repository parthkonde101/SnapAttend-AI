"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prn", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_students_id"), "students", ["id"])
    op.create_index(op.f("ix_students_prn"), "students", ["prn"], unique=True)

    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_teachers_id"), "teachers", ["id"])
    op.create_index(op.f("ix_teachers_teacher_id"), "teachers", ["teacher_id"], unique=True)

    op.create_table(
        "attendance_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_code", sa.String(length=20), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_attendance_sessions_id"), "attendance_sessions", ["id"])
    op.create_index(
        op.f("ix_attendance_sessions_session_code"), "attendance_sessions", ["session_code"], unique=True
    )

    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["attendance_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),
    )
    op.create_index(op.f("ix_attendance_id"), "attendance", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_id"), table_name="attendance")
    op.drop_table("attendance")

    op.drop_index(op.f("ix_attendance_sessions_session_code"), table_name="attendance_sessions")
    op.drop_index(op.f("ix_attendance_sessions_id"), table_name="attendance_sessions")
    op.drop_table("attendance_sessions")

    op.drop_index(op.f("ix_teachers_teacher_id"), table_name="teachers")
    op.drop_index(op.f("ix_teachers_id"), table_name="teachers")
    op.drop_table("teachers")

    op.drop_index(op.f("ix_students_prn"), table_name="students")
    op.drop_index(op.f("ix_students_id"), table_name="students")
    op.drop_table("students")
