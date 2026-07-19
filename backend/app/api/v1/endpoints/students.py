"""Student resource endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_student
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.student import Student
from app.schemas.student import StudentChangePasswordRequest, StudentRead

router = APIRouter()


@router.get("/me", response_model=StudentRead)
def read_current_student(current_student: Student = Depends(get_current_student)) -> Student:
    """Return the profile of the currently authenticated student."""
    return current_student


@router.post("/me/change-password", response_model=StudentRead)
def change_own_password(
    payload: StudentChangePasswordRequest,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
) -> Student:
    """Mandatory (or voluntary) self-service password change. Requires the
    current password — whether that's the administrator-issued default
    (`Test@123`) or one already chosen — as the identity check.

    This is the *only* code path that ever flips `password_changed` back
    to True, which is what the frontend's forced-redirect (see
    `hooks/use-auth.ts`) checks: a student who has never done this stays on
    the mandatory Change Password screen forever; once they have, they
    never see it again, per the spec's explicit "after changing it once,
    they should not see this screen again."
    """
    if not verify_password(payload.current_password, current_student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")

    current_student.password_hash = hash_password(payload.new_password)
    current_student.password_changed = True
    db.add(current_student)
    db.commit()
    db.refresh(current_student)
    return current_student
