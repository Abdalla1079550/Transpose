from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

settings = get_settings()


def _ensure_sqlite_parent_dir() -> None:
    if not settings.database_url.startswith("sqlite:///"):
        return
    raw_path = settings.database_url[len("sqlite:///") :]
    if raw_path == ":memory:":
        return
    db_path = Path(raw_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def _is_sqlite() -> bool:
    return settings.database_url.startswith("sqlite")


def _table_exists(session: Session, table_name: str) -> bool:
    rows = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    )
    return rows.first() is not None


def _sqlite_columns(session: Session, table_name: str) -> set[str]:
    rows = session.exec(text(f"PRAGMA table_info({table_name})"))
    return {str(row[1]) for row in rows.all()}


def _add_column_if_missing(session: Session, table: str, column_name: str, ddl_type: str, default_sql: str | None = None) -> None:
    columns = _sqlite_columns(session, table)
    if column_name in columns:
        return
    default_clause = f" DEFAULT {default_sql}" if default_sql is not None else ""
    session.exec(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {ddl_type}{default_clause}"))


def _run_sqlite_compat_migrations() -> None:
    if not _is_sqlite():
        return

    with Session(engine) as session:
        if _table_exists(session, "student"):
            _add_column_if_missing(session, "student", "name", "TEXT", "''")
            _add_column_if_missing(session, "student", "region_pref", "TEXT")
            _add_column_if_missing(session, "student", "interview_answers_json", "TEXT", "'[]'")
            _add_column_if_missing(session, "student", "skills_json", "TEXT", "'[]'")
            _add_column_if_missing(session, "student", "card_json", "TEXT")
            columns = _sqlite_columns(session, "student")
            if "full_name" in columns:
                session.exec(
                    text(
                        "UPDATE student SET name = COALESCE(NULLIF(name, ''), full_name) "
                        "WHERE full_name IS NOT NULL"
                    )
                )
            if "location" in columns:
                session.exec(
                    text(
                        "UPDATE student SET region_pref = COALESCE(region_pref, location) "
                        "WHERE location IS NOT NULL"
                    )
                )

        if _table_exists(session, "rolequery"):
            _add_column_if_missing(session, "rolequery", "region", "TEXT")
            _add_column_if_missing(session, "rolequery", "raw_desc", "TEXT")
            _add_column_if_missing(session, "rolequery", "skills_must_json", "TEXT", "'[]'")
            _add_column_if_missing(session, "rolequery", "max_grad_year", "INTEGER")
            _add_column_if_missing(session, "rolequery", "source_job_id", "TEXT")
            _add_column_if_missing(session, "rolequery", "source_job_url", "TEXT")
            columns = _sqlite_columns(session, "rolequery")
            if "location" in columns:
                session.exec(
                    text(
                        "UPDATE rolequery SET region = COALESCE(region, location) "
                        "WHERE location IS NOT NULL"
                    )
                )
            if "description" in columns:
                session.exec(
                    text(
                        "UPDATE rolequery SET raw_desc = COALESCE(raw_desc, description) "
                        "WHERE description IS NOT NULL"
                    )
                )

        if _table_exists(session, "match"):
            _add_column_if_missing(session, "match", "role_query_id", "INTEGER")
            _add_column_if_missing(session, "match", "evidence_json", "TEXT", "'[]'")
            _add_column_if_missing(session, "match", "gap_flags_json", "TEXT", "'[]'")
            columns = _sqlite_columns(session, "match")
            if "role_id" in columns:
                session.exec(
                    text(
                        "UPDATE match SET role_query_id = COALESCE(role_query_id, role_id) "
                        "WHERE role_id IS NOT NULL"
                    )
                )

        session.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _run_sqlite_compat_migrations()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
