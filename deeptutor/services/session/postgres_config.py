"""PostgreSQL connection configuration for Dr. Chen AI."""

import os


def get_postgres_url() -> str | None:
    """Return the configured PostgreSQL URL, if available."""
    url = os.environ.get("DATABASE_URL", "").strip()

    if not url:
        return None

    if not url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")

    return url


def connect_postgres():
    """Open a PostgreSQL connection using DATABASE_URL."""
    import psycopg

    url = get_postgres_url()
    if url is None:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(url, connect_timeout=5)


def initialize_postgres_schema():
    """Create DrChenAI database tables if they do not exist."""
    from pathlib import Path

    schema_path = Path(__file__).with_name("postgres_schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    with connect_postgres() as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)
