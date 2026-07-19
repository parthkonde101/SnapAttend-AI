"""Student ORM model."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prn: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Registration intelligence (AI-verified snapshot) -------------------
    # Populated by POST /api/v1/registration/verify, after the student
    # reviews/edits the values the registration pipeline extracted from
    # their ID card. Kept separate from `prn`/`full_name` above (which
    # remain the live, editable account fields) so this stays an audit
    # record of what was verified at registration time, independent of any
    # future profile-editing feature.
    verified_prn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verified_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    id_image_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Local path to the captured ID photo. Development only."
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Administrator System (Milestone 7A) ---------------------------------
    # Nullable/additive, same rationale as Teacher.course: existing student
    # rows predate this field. Nothing in registration, login, or attendance
    # verification reads or writes this column — it exists purely for the
    # admin Student Management table/search (search by PRN, name, or
    # division) and is only ever set by an administrator via
    # `AdminStudentService`.
    division: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Academic Panels & Student Import System -----------------------------
    # See migration 0010_student_roster_fields for the full backfill story.
    # A student belongs to exactly one Panel (nullable/SET NULL so deleting
    # a panel never deletes or orphans a student — see app/models/panel.py).
    panel_id: Mapped[int | None] = mapped_column(
        ForeignKey("panels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    roll_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="Panel-local roll number from the Excel roster import. Not globally unique (PRN is the login "
        "identifier and the only column required to be unique) — two students in different panels may share "
        "the same roll number.",
    )
    batch: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # A brand-new self-registered account already chose its own password, so
    # it defaults to True ("no forced change needed"). Only an Excel import
    # or an administrator's "Reset Password" action ever sets this False —
    # see app/services/excel_import_service.py and
    # AdminStudentService.reset_to_default_password. The student-facing
    # change-password screen is the only thing that ever flips it back to
    # True (see POST /students/me/change-password).
    password_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Soft "still on the official roster" flag, set by the Excel import
    # (re-)upserting a row. Not currently enforced at login — see this
    # milestone's summary for why that's a deliberate, narrow scope
    # decision, not an oversight.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    panel: Mapped["Panel | None"] = relationship(back_populates="students")
    attendance_records: Mapped[list["Attendance"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Student id={self.id} prn={self.prn!r}>"
