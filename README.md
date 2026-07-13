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

## Environment variables

**backend/.env** (see `backend/.env.example`)

| Variable                      | Description                                   |
|--------------------------------|-----------------------------------------------|
| `DATABASE_URL`                 | PostgreSQL connection string                  |
| `SECRET_KEY`                   | JWT signing secret — set a long random value  |
| `ALGORITHM`                    | JWT algorithm (default `HS256`)               |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | Token lifetime in minutes                     |
| `BACKEND_CORS_ORIGINS`         | Comma-separated list of allowed origins       |
| `PROJECT_NAME`, `API_V1_PREFIX`, `ENVIRONMENT` | App metadata          |

**frontend/.env.local** (see `frontend/.env.local.example`)

| Variable                | Description                          |
|--------------------------|---------------------------------------|
| `NEXT_PUBLIC_API_URL`    | Base URL of the FastAPI backend       |

## Docs

- [API reference](docs/API.md)
- [Database schema](docs/DATABASE.md)
