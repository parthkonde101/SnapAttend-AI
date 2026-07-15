"""Administrator management of Teacher accounts (Milestone 7A).

Deliberately a separate service from anything teacher-facing — this never
runs on behalf of a teacher acting on their own account (that's
`app/api/v1/endpoints/teachers.py`'s `/me`), only on behalf of an
authenticated Administrator acting on *any* teacher's account. Password
hashing reuses `app.core.security.hash_password`/`verify_password` exactly
— an admin-created teacher logs in through the exact same
`POST /auth/teacher/login` endpoint that already exists, unmodified.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.attendance_session import AttendanceSession
from app.models.teacher import Teacher
from app.schemas.admin import TeacherAdminRead, TeacherCreateRequest, TeacherUpdateRequest


class TeacherLoginIdTakenError(Exception):
    """Raised when a create/update would collide with another teacher's login id."""


class TeacherHasHistoricalSessionsError(Exception):
    """Raised when a delete is attempted against a teacher who owns one or
    more attendance sessions. Carries the count so the endpoint can return
    an informative message rather than a bare 409."""

    def __init__(self, session_count: int) -> None:
        self.session_count = session_count
        super().__init__(f"Teacher owns {session_count} historical attendance session(s)")


class AdminTeacherService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _session_count(self, teacher_id: int) -> int:
        return int(
            self.db.scalar(select(func.count(AttendanceSession.id)).where(AttendanceSession.teacher_id == teacher_id))
            or 0
        )

    def _to_read(self, teacher: Teacher) -> TeacherAdminRead:
        return TeacherAdminRead(
            id=teacher.id,
            teacher_id=teacher.teacher_id,
            full_name=teacher.full_name,
            course=teacher.course,
            created_at=teacher.created_at,
            session_count=self._session_count(teacher.id),
        )

    def list_teachers(self) -> list[TeacherAdminRead]:
        teachers = list(self.db.scalars(select(Teacher).order_by(Teacher.full_name.asc())))
        return [self._to_read(t) for t in teachers]

    def get_teacher(self, teacher_id: int) -> Teacher:
        teacher = self.db.get(Teacher, teacher_id)
        if teacher is None:
            raise LookupError("Teacher not found")
        return teacher

    def get_teacher_read(self, teacher_id: int) -> TeacherAdminRead:
        return self._to_read(self.get_teacher(teacher_id))

    def create_teacher(self, payload: TeacherCreateRequest) -> TeacherAdminRead:
        existing = self.db.scalar(select(Teacher).where(Teacher.teacher_id == payload.teacher_id))
        if existing is not None:
            raise TeacherLoginIdTakenError(payload.teacher_id)

        teacher = Teacher(
            teacher_id=payload.teacher_id,
            full_name=payload.full_name,
            course=payload.course,
            password_hash=hash_password(payload.password),
        )
        self.db.add(teacher)
        self.db.commit()
        self.db.refresh(teacher)
        return self._to_read(teacher)

    def update_teacher(self, teacher_id: int, payload: TeacherUpdateRequest) -> TeacherAdminRead:
        teacher = self.get_teacher(teacher_id)

        if payload.teacher_id is not None and payload.teacher_id != teacher.teacher_id:
            clash = self.db.scalar(select(Teacher).where(Teacher.teacher_id == payload.teacher_id))
            if clash is not None:
                raise TeacherLoginIdTakenError(payload.teacher_id)
            teacher.teacher_id = payload.teacher_id

        if payload.full_name is not None:
            teacher.full_name = payload.full_name
        if payload.course is not None:
            teacher.course = payload.course

        self.db.add(teacher)
        self.db.commit()
        self.db.refresh(teacher)
        return self._to_read(teacher)

    def reset_password(self, teacher_id: int, new_password: str) -> None:
        teacher = self.get_teacher(teacher_id)
        teacher.password_hash = hash_password(new_password)
        self.db.add(teacher)
        self.db.commit()

    def delete_teacher(self, teacher_id: int) -> None:
        """Refuses to delete a teacher who owns any attendance session,
        historical or active — per this milestone's explicit rule.
        Deliberately checked *before* touching the ORM at all: `Teacher`'s
        own `attendance_sessions` relationship is `cascade="all,
        delete-orphan"` (needed so a legitimately empty teacher's row
        cleans up after itself), so calling `db.delete()` on a teacher with
        sessions would silently cascade-delete their entire attendance
        history instead of raising — exactly what this guard exists to
        prevent.
        """
        teacher = self.get_teacher(teacher_id)
        count = self._session_count(teacher.id)
        if count > 0:
            raise TeacherHasHistoricalSessionsError(count)

        self.db.delete(teacher)
        self.db.commit()
