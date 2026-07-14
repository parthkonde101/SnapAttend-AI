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

## Attendance — Photo Capture

| Method | Path                                 | Auth            | Description                              |
|--------|----------------------------------------|-----------------|--------------------------------------------|
| POST   | `/api/v1/attendance/upload-photo`      | Student token   | Upload a captured ID-card photo             |

Multipart form upload (`file` field). Accepts JPEG, PNG, or WEBP up to 10 MB. The image is
saved as-is to `UPLOAD_DIR` (`backend/uploads/attendance-photos` by default) — nothing is
processed, verified, or linked to a session yet. Response:

```json
{ "success": true, "imageId": "3f9a1c2b7e4d4f0c9a8b1d2e3f4a5b6c" }
```

## Registration — Verified Student Registration

| Method | Path                          | Auth            | Description                                          |
|--------|-------------------------------|-----------------|--------------------------------------------------------|
| POST   | `/api/v1/registration/analyze` | No             | Analyze a captured ID-card photo; extract PRN + name    |
| POST   | `/api/v1/registration/verify`  | Student token  | Persist the reviewed/confirmed PRN + name snapshot      |

`POST /registration/analyze` is a multipart form upload (`file` field, JPEG/PNG/WEBP up to
10 MB), separate from and unrelated to `attendance/upload-photo`. It runs the image through
the registration intelligence pipeline (`backend/app/ai/`): quality validation, preprocessing,
ID-card detection, barcode decoding (tried before OCR), and region-of-interest,
digit-priority OCR for the PRN. If the image fails the quality gate (too small, blurry, too
dark/bright, blown out by glare, or the card isn't fully visible in frame) it is **not saved**,
and `quality_passed` is `false` with human-readable messages in `quality_messages`. Only PRN
and student name are ever extracted — no other fields, and no attendance/session logic is
involved.

Response shape:

```json
{
  "quality_passed": true,
  "quality_messages": [],
  "id_detected": true,
  "barcode": null,
  "prn": "2021BTCS001",
  "student_name": "Amit Kumar Verma",
  "warnings": [],
  "raw_text": ["..."],
  "image_reference": "3f9a1c2b7e4d4f0c9a8b1d2e3f4a5b6c",
  "barcode_type": null,
  "barcode_status": "not_found",
  "barcode_failure_reason": "No barcode found in the frame."
}
```

`prn` and `student_name` may be `null` if extraction couldn't confidently find them — the
frontend always lets the student review and edit both fields before confirming.
`image_reference` is an opaque id for the already-saved photo; pass it back unchanged to
`/registration/verify`.

`barcode_type`, `barcode_status` (one of `not_attempted` / `decoded` / `not_found` / `failed`),
and `barcode_failure_reason` are development-facing only — they exist so barcode decoding can be
observed and tuned independently of OCR, and are not rendered anywhere in the registration UI.
`barcode` itself remains the single field the rest of the app cares about: whatever the barcode
decoded to (if anything), regardless of whether it ended up being used as the PRN.

`POST /registration/verify` is called after account creation (`/auth/student/register`,
unchanged) using the student's fresh token. It accepts the (possibly student-edited) PRN and
name plus the same `image_reference`, and stores them as an immutable verification snapshot
separate from the student's live `prn`/`full_name` fields. This call is best-effort from the
frontend's perspective — if it fails, the account still exists and the student still reaches
their dashboard.

```json
// request
{ "prn": "2021BTCS001", "student_name": "Amit Kumar Verma", "image_reference": "3f9a1c2b7e4d4f0c9a8b1d2e3f4a5b6c" }

// response
{
  "verified_prn": "2021BTCS001",
  "verified_name": "Amit Kumar Verma",
  "id_image_path": "uploads/registration-photos/3f9a1c2b7e4d4f0c9a8b1d2e3f4a5b6c.jpg",
  "verified_at": "2026-07-14T10:05:00Z"
}
```

This pipeline is a registration-time foundation only — it does not implement attendance
verification, session-code recognition, face recognition, or automatic attendance in any form.

## Errors

All error responses share a consistent shape:

```json
{ "detail": "Human readable message" }
```
