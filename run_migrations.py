import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, text


def _ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    target_db = url.database
    if not target_db:
        raise RuntimeError("DATABASE_URL must include a database name")
    if not url.drivername.startswith("postgresql"):
        return

    maintenance_url = url.set(database="postgres")
    maintenance_engine = create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    escaped_db = target_db.replace('"', '""')
    with maintenance_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": target_db},
        ).first()
        if not exists:
            conn.exec_driver_sql(f'CREATE DATABASE "{escaped_db}"')
            print(f"Created database: {target_db}")


def _run_migrations(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    migrations_dir = Path(__file__).parent / "migrations"
    files = sorted([p for p in migrations_dir.glob("*.sql") if p.is_file()])

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        applied = {row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations")).all()}

        for file in files:
            if file.name in applied:
                continue
            sql = file.read_text(encoding="utf-8")
            conn.exec_driver_sql(sql)
            conn.execute(text("INSERT INTO schema_migrations (filename) VALUES (:filename)"), {"filename": file.name})
            print(f"Applied migration: {file.name}")


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in .env")

    try:
        _run_migrations(database_url)
    except OperationalError as exc:
        message = str(exc).lower()
        if "does not exist" not in message:
            raise
        _ensure_database_exists(database_url)
        _run_migrations(database_url)

    print("Migrations completed.")


if __name__ == "__main__":
    main()
