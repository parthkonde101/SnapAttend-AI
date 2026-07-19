"""Administrator management of Panels ("Extending the attendance system"
spec, Parts 2/7 — Academic Panels + Panel Management admin interface).

Plain CRUD, same shape as `AdminCourseService`'s course half. Deleting a
panel does not delete or block anything else — `students.panel_id` and
`attendance_sessions.panel_id` both carry `ondelete="SET NULL"` (see those
models), so any student or historical session referencing a deleted panel
simply becomes "unassigned" rather than losing any other data.

Also owns the panel-course compatibility half ("Assigned Courses" per
panel, via `PanelCourse`) and the panel's roster views — grouped here
rather than in `AdminCourseService`/`AdminStudentService`, mirroring that
service's own choice to keep its teacher-assignment methods on the Course
side: whichever *side* of a relationship an admin screen manages from owns
the service methods for it. The panel detail page (Overview/Courses/
Students/Import Excel) is entirely a panel-side concern.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.sorting import roll_number_sort_key
from app.models.course import Course
from app.models.panel import Panel
from app.models.panel_course import PanelCourse
from app.models.student import Student
from app.schemas.panel import PanelCreateRequest, PanelOverview, PanelUpdateRequest


class PanelNameTakenError(Exception):
    """Raised when a create/update would collide with another panel's name."""


class CourseAlreadyAssignedToPanelError(Exception):
    """Raised when assigning a course to a panel that already has it."""


class AdminPanelService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_panels(self) -> list[Panel]:
        return list(self.db.scalars(select(Panel).order_by(Panel.name.asc())))

    def get_panel(self, panel_id: int) -> Panel:
        panel = self.db.get(Panel, panel_id)
        if panel is None:
            raise LookupError("Panel not found")
        return panel

    def get_overview(self, panel_id: int) -> PanelOverview:
        panel = self.get_panel(panel_id)
        courses = self.list_courses_for_panel(panel_id)
        student_count = int(
            self.db.scalar(select(func.count(Student.id)).where(Student.panel_id == panel_id)) or 0
        )
        return PanelOverview(panel=panel, courses=courses, student_count=student_count)  # type: ignore[arg-type]

    def list_students(self, panel_id: int) -> list[Student]:
        """Not currently called by any endpoint (`GET
        /admin/panels/{id}/students` goes through
        `AdminStudentService.search_students(panel_id=...)` instead, which
        also handles search filtering) — kept as a plain, correct building
        block for this service. Ordered by Roll Number ascending (spec Part
        11 — Student Ordering), numeric-aware, same as every other student
        listing in this codebase."""
        self.get_panel(panel_id)  # 404 if the panel itself doesn't exist
        stmt = select(Student).where(Student.panel_id == panel_id)
        students = list(self.db.scalars(stmt))
        students.sort(key=lambda s: roll_number_sort_key(s.roll_number))
        return students

    def create_panel(self, payload: PanelCreateRequest) -> Panel:
        existing = self.db.scalar(select(Panel).where(Panel.name == payload.name))
        if existing is not None:
            raise PanelNameTakenError(payload.name)

        panel = Panel(name=payload.name, academic_year=payload.academic_year)
        self.db.add(panel)
        self.db.commit()
        self.db.refresh(panel)
        return panel

    def update_panel(self, panel_id: int, payload: PanelUpdateRequest) -> Panel:
        panel = self.get_panel(panel_id)

        if payload.name != panel.name:
            clash = self.db.scalar(select(Panel).where(Panel.name == payload.name))
            if clash is not None:
                raise PanelNameTakenError(payload.name)
            panel.name = payload.name

        panel.academic_year = payload.academic_year

        self.db.add(panel)
        self.db.commit()
        self.db.refresh(panel)
        return panel

    def delete_panel(self, panel_id: int) -> None:
        panel = self.get_panel(panel_id)
        self.db.delete(panel)
        self.db.commit()

    # --- Course assignment ------------------------------------------------
    def list_courses_for_panel(self, panel_id: int) -> list[Course]:
        stmt = (
            select(Course)
            .join(PanelCourse, PanelCourse.course_id == Course.id)
            .where(PanelCourse.panel_id == panel_id)
            .order_by(Course.course_name.asc())
        )
        return list(self.db.scalars(stmt))

    def assign_course_to_panel(self, panel_id: int, course_id: int) -> None:
        panel = self.db.get(Panel, panel_id)
        if panel is None:
            raise LookupError("Panel not found")
        course = self.db.get(Course, course_id)
        if course is None:
            raise LookupError("Course not found")

        existing = self.db.scalar(
            select(PanelCourse).where(PanelCourse.panel_id == panel_id, PanelCourse.course_id == course_id)
        )
        if existing is not None:
            raise CourseAlreadyAssignedToPanelError(f"Panel {panel_id} is already assigned course {course_id}")

        self.db.add(PanelCourse(panel_id=panel_id, course_id=course_id))
        self.db.commit()

    def remove_course_from_panel(self, panel_id: int, course_id: int) -> None:
        link = self.db.scalar(
            select(PanelCourse).where(PanelCourse.panel_id == panel_id, PanelCourse.course_id == course_id)
        )
        if link is None:
            raise LookupError("This panel is not assigned this course")

        # Removing compatibility never touches historical sessions — same
        # rationale as AdminCourseService.remove_course_from_teacher.
        self.db.delete(link)
        self.db.commit()
