"""
api/dependencies.py
────────────────────
FastAPI dependency callables injected via Depends().
"""

from typing import Generator

from sqlalchemy.orm import Session

from database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session; close it when the request finishes."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
