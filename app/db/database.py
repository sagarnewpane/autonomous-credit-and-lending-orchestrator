import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

load_dotenv()
DATABASE_URL = os.getenv("DB_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Example: postgresql://user:password@localhost:5432/gibl_db"
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)


def create_db_and_tables():
    """Create all database tables based on SQLModel models."""
    SQLModel.metadata.create_all(engine)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a DB session per request.

    Usage:
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    with SessionLocal() as session:
        yield session
