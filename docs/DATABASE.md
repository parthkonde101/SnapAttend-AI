# Database Schema

PostgreSQL, managed with SQLAlchemy models and Alembic migrations.

## Tables

**students**
- `id` (PK)
- `prn` (unique, indexed)
- `full_name`
- `password_hash`
- `created_at`

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
