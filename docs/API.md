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

## Attendance — Session Engine

| Method | Path                                | Auth                     | Description                                                        |
|--------|--------------------------------------|---------------------------|---------------------------------------------------------------------|
| POST   | `/api/v1/attendance/start-session`   | Teacher token             | Start a new 90 second session. Terminates any session already active |
| GET    | `/api/v1/attendance/active-session`  | Student or teacher token  | The single system-wide active session, or `{ "active": false }`      |
| POST   | `/api/v1/attendance/end-session`     | Teacher token             | Immediately end the caller's active session                          |
| GET    | `/api/v1/attendance/session-history` | Teacher token             | The current teacher's past sessions, most recent first               |

Only one session may be active system-wide at any time (enforced with a partial unique
database index). Starting a new session automatically deactivates whichever one was
previously active. Sessions expire on their own after `duration_seconds` (90s); expiry is
applied lazily on each request to these endpoints, so poll `GET /active-session` every few
seconds to stay in sync — there is no push/websocket channel in this milestone.

Session codes are 3 characters drawn from `ABCDEFGHJKMNPQRSTUVWXYZ234679` (visually
ambiguous characters such as `0`/`O` and `1`/`I`/`L` are excluded) and are only guaranteed
unique while a session is active — they may be reused by later sessions.

`GET /active-session` response shape:

```json
{
  "active": true,
  "session": {
    "session_id": 12,
    "session_code": "XK7",
    "created_at": "2026-07-14T10:00:00Z",
    "expires_at": "2026-07-14T10:01:30Z",
    "duration_seconds": 90,
    "remaining_seconds": 42,
    "present_count": 0
  }
}
```

## Attendance — Generic CRUD

| Method | Path                              | Auth            | Description                                   |
|--------|------------------------------------|-----------------|------------------------------------------------|
| POST   | `/api/v1/attendance/sessions`      | Teacher token   | Open a new attendance session (custom duration) |
| GET    | `/api/v1/attendance/sessions`      | Teacher token   | List sessions created by the current teacher    |
| GET    | `/api/v1/attendance/sessions/{id}` | Teacher token   | Retrieve a single session                       |
| POST   | `/api/v1/attendance/mark`          | Student token   | **Not implemented** — returns `501`             |

These predate the session engine above and remain available for direct/manual session
management. The student check-in flow (photo capture, OCR, and AI-based verification) is
intentionally left unimplemented. The `/mark` route exists so the contract is stable once
that work begins.

## Errors

All error responses share a consistent shape:

```json
{ "detail": "Human readable message" }
```
