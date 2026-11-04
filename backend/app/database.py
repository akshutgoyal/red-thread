from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_settings.ensure_directories()

_database_url = _settings.resolved_database_url
if _database_url.startswith("sqlite"):
    _engine_kwargs: dict = {"connect_args": {"check_same_thread": False}}
else:
    _engine_kwargs = {
        "connect_args": {"prepare_threshold": None},
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 3,
        "max_overflow": 2,
    }
engine: Engine = create_engine(_database_url, **_engine_kwargs)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    if _database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register all mapped classes)

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    """Add auth ownership columns to pre-auth databases without dropping data."""
    inspector = inspect(engine)
    if "cases" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cases")}
    statements: list[str] = []
    if "owner_id" not in columns:
        statements.append("ALTER TABLE cases ADD COLUMN owner_id VARCHAR(32)")
    if "is_demo" not in columns:
        statements.append("ALTER TABLE cases ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT FALSE")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        # Cases created before account ownership was introduced are the
        # synthetic demos. New user-owned cases always have an owner_id.
        connection.execute(
            text("UPDATE cases SET is_demo = TRUE WHERE owner_id IS NULL")
        )
