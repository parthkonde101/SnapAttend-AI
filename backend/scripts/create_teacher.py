"""CLI utility to create a teacher account.

Teachers do not self-register (only student registration is exposed via
the API), so accounts are provisioned with this script instead.

Usage:
    python -m scripts.create_teacher --teacher-id T001 --full-name "Jane Doe" --password "StrongPass123"
"""
import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.teacher import Teacher


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new teacher account")
    parser.add_argument("--teacher-id", required=True, help="Unique teacher identifier used to log in")
    parser.add_argument("--full-name", required=True, help="Teacher's full name")
    parser.add_argument("--password", required=True, help="Plaintext password (min 8 characters)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Password must be at least 8 characters long.", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        existing = db.scalar(select(Teacher).where(Teacher.teacher_id == args.teacher_id))
        if existing is not None:
            print(f"A teacher with teacher_id={args.teacher_id!r} already exists.", file=sys.stderr)
            raise SystemExit(1)

        teacher = Teacher(
            teacher_id=args.teacher_id,
            full_name=args.full_name,
            password_hash=hash_password(args.password),
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        print(f"Created teacher id={teacher.id} teacher_id={teacher.teacher_id!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
