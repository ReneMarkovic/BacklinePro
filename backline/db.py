# backline/db.py
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import streamlit as st
from sqlmodel import SQLModel, Session, create_engine


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
# Prefer an env var if present; otherwise use a local SQLite file.
# Example Postgres URL:
#   postgresql+psycopg://user:password@host:5432/backline
DEFAULT_SQLITE_DIR = Path("backline_data")
DEFAULT_SQLITE_DIR.mkdir(exist_ok=True)
DEFAULT_SQLITE_PATH = DEFAULT_SQLITE_DIR / "backline.db"

DB_URL = os.getenv("BACKLINE_DB_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")

# For SQLite we need special connect args, and we’ll enable WAL below.
CONNECT_ARGS = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

# ---------------------------------------------------------------------
# Engine factory (cached across reruns & sessions)
# ---------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine(db_url: Optional[str] = None):
    """
    Create (or return cached) SQLAlchemy/SQLModel engine.

    - Cached with st.cache_resource so it’s shared across reruns/sessions.
    - For SQLite: sets journal_mode=WAL, busy_timeout, foreign_keys=ON.
    """
    url = db_url or DB_URL
    engine = create_engine(url, connect_args=CONNECT_ARGS, pool_pre_ping=True)

    if url.startswith("sqlite"):
        # Enable WAL for better concurrent read/write behavior in a web app.
        # WAL is persistent on the database file once set.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=5000;")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")

    return engine


# ---------------------------------------------------------------------
# One-off schema creation (dev / first run)
# ---------------------------------------------------------------------
def create_db_and_tables(db_url: Optional[str] = None) -> None:
    """
    Create all tables defined in SQLModel metadata.

    Call this once on first run or manage schema via Alembic migrations.
    """
    from .db_models import SQLModel as _SQLModel  # ensure import doesn’t recurse
    # NOTE: importing actual models to register metadata
    from . import db_models  # noqa: F401

    engine = get_engine(db_url)
    _SQLModel.metadata.create_all(engine)


# ---------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------
@contextmanager
def get_session(db_url: Optional[str] = None) -> Iterator[Session]:
    """
    Context-managed Session for quick DB usage:

        with get_session() as s:
            s.add(obj)
            s.commit()

    """
    engine = get_engine(db_url)
    with Session(engine) as session:
        yield session
