"""Teacher resource endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher
from app.core.database import get_db
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.teacher_course import TeacherCourse
from app.schemas.course import CourseRead
from app.schemas.teacher import TeacherRead

router = APIRouter()


@router.get("/me", response_model=TeacherRead)
def read_current_teacher(current_teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
    """Return the profile of the currently authenticated teacher."""
    return current_teacher


@router.get("/me/courses", response_model=list[CourseRead])
def read_my_courses(
    db: Session = Depends(get_db), current_teacher: Teacher = Depends(get_current_teacher)
) -> list[Course]:
    """The courses this teacher is assigned to, via the admin-managed
    `TeacherCourse` join — Step 1 of the "Extending the attendance system"
    Session Creation Workflow: a teacher may only start a session against
    one of these. Archived courses are excluded (an admin can still see
    them assigned on the Teachers page, but they no longer appear as a
    session option)."""
    stmt = (
        select(Course)
        .join(TeacherCourse, TeacherCourse.course_id == Course.id)
        .where(TeacherCourse.teacher_id == current_teacher.id, Course.is_archived.is_(False))
        .order_by(Course.course_name.asc())
    )
    return list(db.scalars(stmt))
