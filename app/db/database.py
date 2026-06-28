import os
from typing import Generator

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DB_URL")

engine = None
SessionLocal = None

if DATABASE_URL:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker
        from sqlmodel import SQLModel

        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            future=True,
        )

        SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    except Exception as e:
        print(f"⚠️  Could not initialize SQLAlchemy engine: {e}")


def create_db_and_tables():
    if engine is None:
        return
    try:
        from sqlmodel import SQLModel

        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"⚠️  Could not create tables via SQLAlchemy: {e}")


def get_db() -> Generator:
    if SessionLocal is None:
        raise RuntimeError(
            "Direct database connection not available. "
            "Set DB_URL or use the Supabase client."
        )
    with SessionLocal() as session:
        yield session
