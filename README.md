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
| `PROJECT_NAME`, `API_V1_PREFIX`, `ENVIRONMENT` | App metadata          |

**frontend/.env.local** (see `frontend/.env.local.example`)

| Variable                | Description                          |
|--------------------------|---------------------------------------|
| `NEXT_PUBLIC_API_URL`    | Base URL of the FastAPI backend — localhost for dev, your LAN IP for phone testing, your real domain in production |

## Docs

- [API reference](docs/API.md)
- [Database schema](docs/DATABASE.md)
