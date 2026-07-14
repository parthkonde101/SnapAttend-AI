"""Student ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, String, func
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

    attendance_records: Mapped[list["Attendance"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Student id={self.id} prn={self.prn!r}>"
