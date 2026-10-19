from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
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
