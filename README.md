# SnapAttend AI

Full-stack attendance management platform. Next.js 15 + FastAPI + PostgreSQL monorepo.

Attendance capture (photo/OCR/AI verification) is intentionally not implemented yet — this
milestone ships accounts, authentication, and the dashboard shells that feature will plug into.

## Stack

- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Auth**: JWT (python-jose), bcrypt password hashing (passlib)

## Project structure

```
snapattend-ai/
├── backend/         FastAPI app, SQLAlchemy models, Alembic migrations
├── frontend/         Next.js app (App Router)
└── docs/              API and database reference
```

## Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 14+

## Backend setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then edit DATABASE_URL / SECRET_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Interactive API docs: `http://localhost:8000/api/v1/docs`.

To test from a phone on the same Wi-Fi (LAN testing), bind to all interfaces and add your LAN
origin to CORS:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# backend/.env
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.1.42:3000
```

(Replace `192.168.1.42` with your computer's LAN IP.)

Teachers don't self-register. Create one with:

```bash
python -m scripts.create_teacher --teacher-id T001 --full-name "Jane Doe" --password "StrongPass123"
```

### Registration intelligence pipeline (optional, Tesseract by default)

Student registration (`/student/register`) captures a photo of the student's ID card and runs
it through `backend/app/ai/` — image quality checks (resolution/blur/brightness/glare/full-card
visibility), preprocessing, barcode decoding, region-of-interest OCR, and PRN validation —
before the student reviews/edits the result and confirms.

PRN extraction tries, in order: (1) the barcode payload, if one decodes and looks like a
plausible PRN (`app/ai/ocr.is_plausible_prn`) — barcode decoding always runs before OCR, since
it's cheap and precise when the card has one; (2) digit-priority OCR over a small, enhanced crop
of the region most likely to contain the PRN (`app/ai/roi.py` — anchored to the barcode's own
location when one was found, otherwise a set of generic, configurable fallback bands); (3)
digit-priority OCR over the whole image as a last resort. Every candidate found this way is
scored (length fit, digit density, proximity to a "PRN"/"Reg No" label) and the strongest one
wins — manual entry is only needed when nothing scores as plausible. None of this is tied to a
specific institution's card layout: region positions are fractions of the card (or offsets from
the barcode), not fixed coordinates, and are tunable via environment variables in
`app/ai/config.py` without touching any pipeline code.

This is isolated from the rest of the backend behind a single factory function
(`app/ai/ocr.get_ocr_engine`), so the OCR engine is fully swappable — `app/ai/ocr.py` currently
ships two implementations of the same `OcrEngine` interface (`TesseractOcrEngine`, the default,
and `PaddleOcrEngine`, opt-in); EasyOCR, Google Vision, or Azure Vision can be added the same
way without touching any other module.

For development, set `SNAPATTEND_AI_DEBUG=1` to save every intermediate image (preprocessed
frame, each candidate PRN-region crop, its enhanced version) to
`SNAPATTEND_AI_DEBUG_DIR` (default `backend/uploads/registration-debug`) for tuning against real
ID cards. Off by default — never required in production. `RegistrationAnalysis` also always
includes `barcode_type` / `barcode_status` / `barcode_failure_reason` for observing barcode
decoding independently of OCR; these are development-facing fields, not shown in the
registration UI.

`pytesseract` (listed in `requirements.txt`) is a thin wrapper around the system `tesseract`
binary, chosen as the default because it installs identically on every Python version and
platform — including Python 3.13 on Apple Silicon — with no large ML framework wheel to chase.
It's imported lazily: the API boots fine without the binary installed, it just can't run OCR
(registration then always falls back to blank PRN/name fields for manual entry).

```bash
brew install tesseract   # macOS
apt-get install tesseract-ocr # Debian/Ubuntu
```

Barcode decoding (`pyzbar`) additionally needs the system `zbar` library:

```bash
brew install zbar        # macOS
apt-get install libzbar0 # Debian/Ubuntu
```

PaddleOCR remains available as an alternative engine (see the commented block in
`requirements.txt`) but isn't installed by default — `paddlepaddle` is a much heavier,
native-code dependency, and its wheel availability for new Python releases and Apple Silicon
has historically lagged.

None of these dependencies are required for any other part of the app — authentication,
sessions, and attendance photo capture do not touch `app/ai` at all.

## Frontend setup

```bash
cd frontend
npm install

cp .env.local.example .env.local   # then edit NEXT_PUBLIC_API_URL if needed

npm run dev
```

Frontend runs at `http://localhost:3000`.

For LAN testing (loading the app on a phone), run `npm run dev:lan` instead of `npm run dev` —
it binds Next.js to `0.0.0.0` so devices on the same Wi-Fi can reach it — and point
`NEXT_PUBLIC_API_URL` at your computer's LAN IP (see `frontend/.env.local.example`). Note that
mobile browsers only grant camera access (`getUserMedia`) on secure contexts — `localhost` is
exempt, but a plain `http://192.168.x.x` origin is not, so the Smart Camera Capture screen won't
be able to open the camera over LAN without HTTPS (e.g. a tool like `mkcert` or `ngrok`). The
rest of the app works fine over plain HTTP on LAN.

## Environment variables

**backend/.env** (see `backend/.env.example`)

| Variable                      | Description                                   |
|--------------------------------|-----------------------------------------------|
| `DATABASE_URL`                 | PostgreSQL connection string                  |
| `SECRET_KEY`                   | JWT signing secret — set a long random value  |
| `ALGORITHM`                    | JWT algorithm (default `HS256`)               |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | Token lifetime in minutes                     |
| `BACKEND_CORS_ORIGINS`         | Comma-separated list of allowed origins (add your LAN origin for phone testing) |
| `UPLOAD_DIR`                   | Local folder where attendance photos are stored |
| `REGISTRATION_UPLOAD_DIR`      | Local folder where verified registration ID photos are stored |
| `PROJECT_NAME`, `API_V1_PREFIX`, `ENVIRONMENT` | App metadata          |

**frontend/.env.local** (see `frontend/.env.local.example`)

| Variable                | Description                          |
|--------------------------|---------------------------------------|
| `NEXT_PUBLIC_API_URL`    | Base URL of the FastAPI backend — localhost for dev, your LAN IP for phone testing, your real domain in production |

## Docs

- [API reference](docs/API.md)
- [Database schema](docs/DATABASE.md)
