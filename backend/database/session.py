from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql+psycopg2://qatra:qatra@localhost:5432/qatra")


class Base(DeclarativeBase):
    pass


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_schema() -> None:
    # Models are imported here so metadata includes every relationship.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
