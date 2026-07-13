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
- `session_code` (unique, indexed)
- `teacher_id` (FK -> teachers.id, cascade delete)
- `expires_at`
- `is_active`
- `created_at`

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
