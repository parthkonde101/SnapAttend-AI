"""Administrator endpoints (Milestone 7A — Administrator System).

Every route in this router is gated by `get_current_admin` — a teacher or
student bearer token is rejected exactly like no token at all (see
`app/api/deps.py`). Nothing here modifies the AI pipelines, verification
philosophy, diagnostics logic, or the teacher-facing review/export
surfaces; where this router needs the same data teachers already see
(session review, photos, Excel export), it calls the exact same service
functions those endpoints call, through two small additive methods on
`AttendanceReviewService` (`get_session_for_admin`, `set_status_as_admin`)
that exist purely to drop the teacher-ownership scoping — see that
module's docstrings.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models.admin import Admin
from app.schemas.admin import (
    AdminPasswordResetRequest,
    AdminRead,
    AdminSessionDeleteConfirmation,
    AdminSessionDeleteRequest,
    AdminSessionListItem,
    DashboardStats,
    SimpleSuccessResponse,
    StudentAdminRead,
    StudentProfile,
    StudentUpdateRequest,
    TeacherAdminRead,
    TeacherCreateRequest,
    TeacherDeleteBlockedResponse,
    TeacherUpdateRequest,
)
from app.schemas.attendance import AttendanceOverrideRequest, SessionReviewResponse, StudentAttendanceReviewItem
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.admin_session_service import AdminSessionService, InvalidDeleteConfirmationError
from app.services.admin_student_service import AdminStudentService, StudentPrnTakenError
from app.services.admin_teacher_service import (
    AdminTeacherService,
    TeacherHasHistoricalSessionsError,
    TeacherLoginIdTakenError,
)
from app.services.attendance_export_service import build_attendance_export
from app.services.attendance_review_service import AttendanceReviewService

router = APIRouter()


@router.get("/me", response_model=AdminRead)
def read_current_admin(current_admin: Admin = Depends(get_current_admin)) -> Admin:
    return current_admin


# --- Dashboard ---------------------------------------------------------------


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> DashboardStats:
    return AdminDashboardService(db).get_stats()


# --- Teacher management --------------------------------------------------------


@router.get("/teachers", response_model=list[TeacherAdminRead])
def list_teachers(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)) -> list[TeacherAdminRead]:
    return AdminTeacherService(db).list_teachers()


@router.post("/teachers", response_model=TeacherAdminRead, status_code=status.HTTP_201_CREATED)
def create_teacher(
    payload: TeacherCreateRequest, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> TeacherAdminRead:
    try:
        return AdminTeacherService(db).create_teacher(payload)
    except TeacherLoginIdTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Login ID '{exc}' is already in use.") from exc


@router.get("/teachers/{teacher_id}", response_model=TeacherAdminRead)
def get_teacher(
    teacher_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> TeacherAdminRead:
    try:
        return AdminTeacherService(db).get_teacher_read(teacher_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/teachers/{teacher_id}", response_model=TeacherAdminRead)
def update_teacher(
    teacher_id: int,
    payload: TeacherUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> TeacherAdminRead:
    try:
        return AdminTeacherService(db).update_teacher(teacher_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TeacherLoginIdTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Login ID '{exc}' is already in use.") from exc


@router.post("/teachers/{teacher_id}/reset-password", response_model=SimpleSuccessResponse)
def reset_teacher_password(
    teacher_id: int,
    payload: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> SimpleSuccessResponse:
    try:
        AdminTeacherService(db).reset_password(teacher_id, payload.new_password)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SimpleSuccessResponse()


@router.delete("/teachers/{teacher_id}", response_model=SimpleSuccessResponse)
def delete_teacher(
    teacher_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> SimpleSuccessResponse:
    try:
        AdminTeacherService(db).delete_teacher(teacher_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TeacherHasHistoricalSessionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This teacher has {exc.session_count} historical attendance session(s) and cannot be deleted. "
                "Historical attendance records must never become orphaned."
            ),
        ) from exc
    return SimpleSuccessResponse()


# --- Student management --------------------------------------------------------


@router.get("/students", response_model=list[StudentAdminRead])
def search_students(
    query: str | None = None, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> list[StudentAdminRead]:
    """`query` matches PRN, name, or division (case-insensitive substring) — see AdminStudentService.search_students."""
    return AdminStudentService(db).search_students(query)


@router.get("/students/{student_id}", response_model=StudentProfile)
def get_student_profile(
    student_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> StudentProfile:
    try:
        return AdminStudentService(db).get_profile(student_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/students/{student_id}/registration-photo")
def get_student_registration_photo(
    student_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> FileResponse:
    """Serves the student's captured ID-card photo from registration —
    this is the one stored image on a Student row (`id_image_path`), so it
    answers both the "View ID Card" and "View Registration Photo" actions
    the milestone lists (there is only one registration image in this
    system, not two)."""
    try:
        path = AdminStudentService(db).get_registration_photo_path(student_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/jpeg")


@router.put("/students/{student_id}", response_model=StudentAdminRead)
def update_student(
    student_id: int,
    payload: StudentUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> StudentAdminRead:
    try:
        return AdminStudentService(db).update_student(student_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StudentPrnTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"PRN '{exc}' is already in use.") from exc


@router.post("/students/{student_id}/reset-password", response_model=SimpleSuccessResponse)
def reset_student_password(
    student_id: int,
    payload: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> SimpleSuccessResponse:
    try:
        AdminStudentService(db).reset_password(student_id, payload.new_password)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SimpleSuccessResponse()


@router.delete("/students/{student_id}", response_model=SimpleSuccessResponse)
def delete_student(
    student_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> SimpleSuccessResponse:
    try:
        AdminStudentService(db).delete_student(student_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SimpleSuccessResponse()


# --- Attendance session management ----------------------------------------------


@router.get("/sessions", response_model=list[AdminSessionListItem])
def list_sessions(db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)) -> list[AdminSessionListItem]:
    return AdminSessionService(db).list_sessions()


@router.get("/sessions/{session_id}/delete-confirmation", response_model=AdminSessionDeleteConfirmation)
def get_session_delete_confirmation(
    session_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> AdminSessionDeleteConfirmation:
    try:
        return AdminSessionService(db).get_delete_confirmation(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", response_model=SimpleSuccessResponse)
def delete_session(
    session_id: int,
    payload: AdminSessionDeleteRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> SimpleSuccessResponse:
    try:
        AdminSessionService(db).delete_session(session_id, confirmation=payload.confirmation)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDeleteConfirmationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Type "DELETE" exactly to confirm permanent deletion.'
        ) from exc
    return SimpleSuccessResponse()


# --- Attendance session review (reuses the existing teacher review engine) ------


@router.get("/sessions/{session_id}/review", response_model=SessionReviewResponse)
def get_admin_session_review(
    session_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> SessionReviewResponse:
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_admin(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return review_service.build_session_review(session)


@router.post("/sessions/{session_id}/override", response_model=StudentAttendanceReviewItem)
def override_admin_session_status(
    session_id: int,
    payload: AttendanceOverrideRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> StudentAttendanceReviewItem:
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_admin(session_id)
        return review_service.set_status_as_admin(session=session, student_id=payload.student_id, status=payload.status)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/photo/{student_id}")
def get_admin_session_photo(
    session_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
) -> FileResponse:
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_admin(session_id)
        path = review_service.get_photo_path(session=session, student_id=student_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/jpeg")


@router.get("/sessions/{session_id}/export")
def export_admin_session(
    session_id: int, db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
) -> Response:
    review_service = AttendanceReviewService(db)
    try:
        session = review_service.get_session_for_admin(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if session.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session is still active. End it before exporting the final attendance list.",
        )

    export = build_attendance_export(db, session)
    return Response(
        content=export.content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
