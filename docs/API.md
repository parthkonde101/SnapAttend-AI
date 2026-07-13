# API Reference

Base URL: `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL` on the frontend).
All endpoints are namespaced under `/api/v1`. Interactive docs are served at `/api/v1/docs`.

## Authentication

| Method | Path                          | Auth | Description                              |
|--------|-------------------------------|------|-------------------------------------------|
| POST   | `/api/v1/auth/student/register` | No | Create a student account, returns a JWT   |
| POST   | `/api/v1/auth/student/login`    | No | Log in as a student, returns a JWT        |
| POST   | `/api/v1/auth/teacher/login`    | No | Log in as a teacher, returns a JWT        |

Teachers are provisioned with `backend/scripts/create_teacher.py` — there is no public
teacher registration endpoint.

Tokens are returned as `{ "access_token": "...", "token_type": "bearer" }` and must be sent
as `Authorization: Bearer <token>` on subsequent requests.

## Students

| Method | Path                  | Auth            | Description                     |
|--------|-----------------------|-----------------|----------------------------------|
| GET    | `/api/v1/students/me` | Student token   | Current student's profile        |

## Teachers

| Method | Path                  | Auth            | Description                     |
|--------|-----------------------|-----------------|----------------------------------|
| GET    | `/api/v1/teachers/me` | Teacher token   | Current teacher's profile        |

## Attendance

| Method | Path                              | Auth            | Description                                   |
|--------|------------------------------------|-----------------|------------------------------------------------|
| POST   | `/api/v1/attendance/sessions`      | Teacher token   | Open a new attendance session                  |
| GET    | `/api/v1/attendance/sessions`      | Teacher token   | List sessions created by the current teacher    |
| GET    | `/api/v1/attendance/sessions/{id}` | Teacher token   | Retrieve a single session                       |
| POST   | `/api/v1/attendance/mark`          | Student token   | **Not implemented** — returns `501`             |

The student check-in flow (photo capture, OCR, and AI-based verification) is intentionally
left unimplemented. The route exists so the contract is stable once that work begins.

## Errors

All error responses share a consistent shape:

```json
{ "detail": "Human readable message" }
```
