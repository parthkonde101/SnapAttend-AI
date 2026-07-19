"""Administrator management of Courses and Course->Teacher assignments
(Milestone 8A — Course Normalization).

Parallel in shape to `AdminTeacherService`/`AdminPanelService`: plain CRUD
over one table, plus (unique to this service) the assign/remove operations
over the `TeacherCourse` join table — "Assign Courses to Teachers, Remove
Course Assignments" from the milestone spec, grouped here rather than in
`AdminTeacherService` since it's fundamentally a Course-side concern (the
same pattern as an e-commerce admin managing "which categories a product
belongs to" from the category screen).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.teacher import Teacher
from app.models.teacher_course import TeacherCourse
from app.schemas.course import CourseCreateRequest, CourseUpdateRequest


class CourseCodeTakenError(Exception):
    """Raised when a create/update would collide with another course's course_code."""


class CourseAlreadyAssignedError(Exception):
    """Raised when assigning a course to a teacher who already has it."""


class AdminCourseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Course CRUD -----------------------------------------------------------
    def list_courses(self, *, include_archived: bool = True) -> list[Course]:
        """`include_archived=True` (the admin Manage Courses screen's own
        listing) shows every course, archived or not — an admin still
        needs to find and unarchive one. `include_archived=False` is for
        every *picker* (teacher's assigned-courses checklist, panel's
        course-assignment checklist) — Milestone 8B's "Archive Course"
        removes a course from being newly assignable without touching
        anything it's already assigned to."""
        stmt = select(Course).order_by(Course.course_name.asc())
        if not include_archived:
            stmt = stmt.where(Course.is_archived.is_(False))
        return list(self.db.scalars(stmt))

    def get_course(self, course_id: int) -> Course:
        course = self.db.get(Course, course_id)
        if course is None:
            raise LookupError("Course not found")
        return course

    def create_course(self, payload: CourseCreateRequest) -> Course:
        existing = self.db.scalar(select(Course).where(Course.course_code == payload.course_code))
        if existing is not None:
            raise CourseCodeTakenError(payload.course_code)

        course = Course(course_code=payload.course_code, course_name=payload.course_name)
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def update_course(self, course_id: int, payload: CourseUpdateRequest) -> Course:
        course = self.get_course(course_id)

        if payload.course_code is not None and payload.course_code != course.course_code:
            clash = self.db.scalar(select(Course).where(Course.course_code == payload.course_code))
            if clash is not None:
                raise CourseCodeTakenError(payload.course_code)
            course.course_code = payload.course_code

        if payload.course_name is not None:
            course.course_name = payload.course_name

        if payload.is_archived is not None:
            course.is_archived = payload.is_archived

        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete_course(self, course_id: int) -> None:
        """Deletes the course. `TeacherCourse` rows referencing it cascade
        (`ondelete="CASCADE"` — see that model), and any historical
        `AttendanceSession.course_id` pointing at it is set to NULL
        (`ondelete="SET NULL"` — see `AttendanceSession`), never deleting
        attendance history itself."""
        course = self.get_course(course_id)
        self.db.delete(course)
        self.db.commit()

    # --- Teacher assignment ---------------------------------------------------
    def list_teacher_ids_for_course(self, course_id: int) -> list[int]:
        return list(self.db.scalars(select(TeacherCourse.teacher_id).where(TeacherCourse.course_id == course_id)))

    def assign_course_to_teacher(self, teacher_id: int, course_id: int) -> None:
        teacher = self.db.get(Teacher, teacher_id)
        if teacher is None:
            raise LookupError("Teacher not found")
        course = self.db.get(Course, course_id)
        if course is None:
            raise LookupError("Course not found")

        existing = self.db.scalar(
            select(TeacherCourse).where(
                TeacherCourse.teacher_id == teacher_id, TeacherCourse.course_id == course_id
            )
        )
        if existing is not None:
            raise CourseAlreadyAssignedError(f"Teacher {teacher_id} is already assigned course {course_id}")

        self.db.add(TeacherCourse(teacher_id=teacher_id, course_id=course_id))
        self.db.commit()

    def remove_course_from_teacher(self, teacher_id: int, course_id: int) -> None:
        link = self.db.scalar(
            select(TeacherCourse).where(
                TeacherCourse.teacher_id == teacher_id, TeacherCourse.course_id == course_id
            )
        )
        if link is None:
            raise LookupError("This teacher is not assigned to this course")

        # Milestone 8A: unassigning a teacher from a course never touches
        # any attendance session they've already started for it — a
        # session's own `course_id` is independent of the live
        # TeacherCourse assignment, exactly like removing a Panel never
        # touches historical sessions that already reference it (both use
        # `ondelete="SET NULL"` for the *session* side, but this delete is
        # only against `teacher_courses`, which has no bearing on
        # `attendance_sessions` at all).
        self.db.delete(link)
        self.db.commit()

    def get_teachers_for_course_count(self, course_id: int) -> int:
        return len(self.list_teacher_ids_for_course(course_id))
