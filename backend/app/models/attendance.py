"""Attendance ORM model.

Records that a given student was marked present for a given attendance
session, verified by the Attendance Verification Engine
(`app.ai.attendance_pipeline`) — identity confirmed against the student's
own registered ID card and the projected session marker confirmed against
the captured scene. See `app/services/attendance_verification_service.py`
for how these rows get created.

The unique constraint below is the hard backstop that guarantees "only one
row per (student, session)" — a second successful *AI* verification attempt
hits it and is turned into a friendly "already recorded" response by the
service layer, never a second row. Failed AI attempts never reach this
table at all, so they never consume a student's remaining attempts.

Since the teacher-review milestone, this row's `status` is the *current
effective* attendance status, not "this student was verified present" —
see `app/services/attendance_review_service.py`. A teacher's Present/Absent
override flips `status` in place rather than deleting/recreating the row,
so a student who was genuinely AI-verified and later overridden to
"absent" keeps their original photo/marker/confidence evidence intact
(non-destructive, per that milestone's explicit requirement) — only
`status` and the `overridden_*` audit columns change. A student manually
marked "present" by a teacher with no matching AI attempt gets a row with
no AI evidence at all (`marker_detected_character`/`image_reference` etc.
stay null) and `is_teacher_override=True`.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False
    )
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Attendance Verification Engine (V1) ---------------------------------
    verification_source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="ocr",
        doc="How the student's PRN was read: 'barcode', 'ocr', or 'teacher_override' for a manual mark.",
    )
    marker: Mapped[str] = mapped_column(
        String(1), nullable=False, server_default="A", doc="The session marker expected at the time of this attempt."
    )
    verification_duration_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Total pipeline processing time for the successful attempt."
    )
    image_reference: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Opaque id of the stored capture. Powers the teacher review photo viewer."
    )

    # --- Verification philosophy refinement (teacher review milestone) -------
    # See app/services/attendance_verification_service.py's decision logic
    # and app/ai/attendance_config.py's MARKER_DISPLAY_CONFIDENCE_* tiers for
    # what populates these. Null/default on teacher-override rows with no AI
    # attempt behind them.
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="present",
        doc="Current effective status: 'present' or 'absent'. See this model's docstring.",
    )
    marker_detected_character: Mapped[str | None] = mapped_column(
        String(1),
        nullable=True,
        doc="Raw OCR output for this attempt, if any — may differ from `marker`, or be null if OCR read nothing.",
    )
    marker_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="OCR confidence (0-1) for marker_detected_character. Null if OCR found nothing."
    )
    display_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether a glyph-shaped region was geometrically isolated on a real classroom display, "
        "independent of whether OCR read it correctly.",
    )
    display_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0.0",
        doc="0.0/0.3/0.6/1.0 geometric evidence tier — see MARKER_DISPLAY_CONFIDENCE_* in app.ai.attendance_config.",
    )
    marker_verification_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="exact_match",
        doc="'exact_match' (OCR matched the session marker), 'display_evidence' (accepted leniently on "
        "identity + classroom-display evidence), or 'teacher_override' (no AI attempt at all).",
    )
    is_teacher_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", doc="True if a teacher, not the AI pipeline, set the current status."
    )
    overridden_by_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, doc="Teacher who last changed `status`, if any."
    )
    overridden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When `status` was last changed by a teacher."
    )

    student: Mapped["Student"] = relationship(back_populates="attendance_records")
    session: Mapped["AttendanceSession"] = relationship(back_populates="attendance_records")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attendance id={self.id} student_id={self.student_id} session_id={self.session_id} status={self.status!r}>"
