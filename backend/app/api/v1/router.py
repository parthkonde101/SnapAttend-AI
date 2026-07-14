"""Aggregates all v1 endpoint routers under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import attendance, auth, diagnostics, registration, students, teachers

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(registration.router, prefix="/registration", tags=["registration"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["diagnostics"])
