# Database Schema

PostgreSQL, managed with SQLAlchemy models and Alembic migrations.

## Tables

**students**
- `id` (PK)
- `prn` (unique, indexed)
- `full_name`
- `password_hash`
- `created_at`
- `verified_prn` (nullable) — PRN as extracted/confirmed during ID-verified registration
- `verified_name` (nullable) — student name as extracted/confirmed during ID-verified registration
- `id_image_path` (nullable) — local path to the captured ID photo (development only)
- `verified_at` (nullable) — timestamp the registration snapshot was saved

The `verified_*` columns are an additive audit snapshot written once by
`POST /api/v1/registration/verify` (see `docs/API.md`) — they are intentionally kept separate
from the live `prn`/`full_name` fields rather than replacing them, so the account's primary
identity fields and the AI-verified snapshot can evolve independently later (e.g. if profile
editing is added). Added in migration `0003_registration_verification`.

**teachers**
- `id` (PK)
- `teacher_id` (unique, indexed)
- `full_name`
- `password_hash`
- `created_at`

**attendance_sessions**
- `id` (PK)
- `session_code` (indexed, not globally unique — only guaranteed unique while active)
- `teacher_id` (FK -> teachers.id, cascade delete)
- `duration_seconds` (fixed at 90 by the session engine)
- `expires_at`
- `is_active`
- `created_at`
- Partial unique index `uq_attendance_sessions_single_active` on `is_active` (`WHERE is_active = true`) —
  guarantees at most one active session system-wide

**attendance**
- `id` (PK)
- `student_id` (FK -> students.id, cascade delete)
- `session_id` (FK -> attendance_sessions.id, cascade delete)
- `marked_at`
- Unique constraint on `(student_id, session_id)` — a student can only be marked once per session

## Relationships

- `Teacher 1—N AttendanceSession`
- `AttendanceSession 1—N Attendance`
- `Student 1—N Attendance`

## Migrations

```bash
cd backend
alembic upgrade head                 # apply migrations
alembic revision --autogenerate -m "message"   # generate a new migration after model changes
```
