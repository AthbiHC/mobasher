"""
Database engine and session management for Mobasher.

Provides:
- Pydantic settings-driven DATABASE_URL
- SQLAlchemy engine with sensible pooling
- Session factory and context helper
"""

from __future__ import annotations

from typing import Generator, Optional
from urllib.parse import urlencode

from pydantic_settings import BaseSettings
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import event


class DBSettings(BaseSettings):
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="mobasher", alias="DB_NAME")
    db_user: str = Field(default="mobasher", alias="DB_USER")
    db_password: str = Field(default="mobasher", alias="DB_PASSWORD")
    db_sslmode: Optional[str] = Field(default=None, alias="DB_SSLMODE")  # e.g., require/disable
    db_schema: Optional[str] = Field(default=None, alias="DB_SCHEMA")  # optional: set search_path

    model_config = {"extra": "ignore", "env_file": ".env", "case_sensitive": False}

    def database_url(self) -> str:
        # Build a PostgreSQL URL compatible with psycopg
        base = f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        params: dict[str, str] = {}
        if self.db_sslmode:
            params["sslmode"] = str(self.db_sslmode)
        if self.db_schema:
            # Use 'options' to set search_path; URL-encode as needed
            params["options"] = f"-csearch_path={self.db_schema}"
        if params:
            return f"{base}?{urlencode(params)}"
        return base


_engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None


def init_engine(settings: Optional[DBSettings] = None) -> Engine:
    """Initialize and return a global SQLAlchemy engine."""
    global _engine, SessionLocal
    if settings is None:
        settings = DBSettings()
    if _engine is None:
        _engine = create_engine(
            settings.database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
        # Ensure UTF-8 client encoding on every connection
        @event.listens_for(_engine, "connect")
        def _set_client_encoding(dbapi_connection, connection_record):  # type: ignore[no-redef]
            try:
                cur = dbapi_connection.cursor()
                cur.execute("SET client_encoding TO 'UTF8'")
                cur.close()
            except Exception:
                # Best-effort; psycopg3 should already use UTF-8
                pass
        SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
        )
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Context-yielding DB session for scripts and web contexts.

    Usage:
        with contextlib.closing(next(get_session())) as db:
            ...
    or FastAPI dependency injection pattern can wrap this generator.
    """
    global SessionLocal
    if SessionLocal is None:
        init_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Create tables from SQLAlchemy models (useful in early dev; prefer Alembic later)."""
    from .models import Base  # local import to avoid circulars

    eng = init_engine()
    Base.metadata.create_all(bind=eng)


