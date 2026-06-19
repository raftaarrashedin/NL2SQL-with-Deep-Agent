from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
database_url = settings.resolved_database_url

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
