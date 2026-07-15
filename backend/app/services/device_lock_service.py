"""Temporary device lock (Milestone 6C — Production Security & Classroom
Lockdown, Part 1).

Purpose: stop one physical phone from marking attendance for multiple
different student accounts within the same attendance session — e.g. one
student passing their phone around so several classmates "attend" without
actually being present. This is deliberately NOT a device-binding feature:
nothing here ever remembers a device beyond the session it was used in, and
a device is never associated with a student until that student's
attendance has actually, successfully been recorded (see the `/mark`
endpoint in `app/api/v1/endpoints/attendance.py`, the only caller of
`record_lock`).

Kept as its own tiny service (not folded into
`AttendanceVerificationService`) so the identity/marker decision logic in
that file — the part of the codebase under the most scrutiny — stays
untouched by this milestone. The device-lock check is a request-level gate
the endpoint applies *before* even considering the AI verification
pipeline, exactly like the pre-existing "already marked" cheap early exit
it sits alongside.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance_device_lock import AttendanceDeviceLock

# Friendly, non-technical explanation shown to the student — never mentions
# "device fingerprint", "fraud", or anything that would sound like an
# accusation to a legitimate student who is simply sharing a phone with a
# sibling, or whose own retry landed on someone else's still-locked device.
DEVICE_ALREADY_USED_MESSAGE = (
    "This device has already been used to mark attendance for another student during this "
    "attendance session. Please ask that student to use a different device, or wait for the "
    "next session."
)


class DeviceLockService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_lock(self, *, session_id: int, device_id: str) -> AttendanceDeviceLock | None:
        return self.db.scalar(
            select(AttendanceDeviceLock).where(
                AttendanceDeviceLock.session_id == session_id,
                AttendanceDeviceLock.device_id == device_id,
            )
        )

    def is_blocked(self, *, session_id: int, device_id: str, student_id: int) -> bool:
        """True only for "different student, same device, same active
        session". A device with no lock yet, or one already locked to this
        exact student (accidental logout, app restart, browser refresh,
        logging back in — all fine), is never blocked."""
        lock = self._get_lock(session_id=session_id, device_id=device_id)
        return lock is not None and lock.student_id != student_id

    def record_lock(self, *, session_id: int, device_id: str, student_id: int) -> None:
        """Create the lock once a student's attendance has actually been
        recorded. A no-op if this exact (session, device) pair is already
        locked — including to the same student re-confirming — so this is
        always safe to call after every successful mark."""
        if self._get_lock(session_id=session_id, device_id=device_id) is not None:
            return

        lock = AttendanceDeviceLock(session_id=session_id, device_id=device_id, student_id=student_id)
        self.db.add(lock)
        try:
            self.db.commit()
        except IntegrityError:
            # Lost a race with a concurrent first-success from the same
            # device between the check above and this commit. Either way a
            # lock now exists for this (session, device) — nothing further
            # to do.
            self.db.rollback()

    def clear_locks_for_session(self, *, session_id: int) -> None:
        """Wipe every temporary lock for one session — called whenever that
        session stops being the active one (teacher ends it, it expires
        naturally, or a new session supersedes it). No permanent
        device/student relationship should ever survive past this."""
        self.db.execute(delete(AttendanceDeviceLock).where(AttendanceDeviceLock.session_id == session_id))
        self.db.commit()
