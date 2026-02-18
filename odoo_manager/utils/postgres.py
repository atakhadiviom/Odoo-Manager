"""
PostgreSQL utility functions.
"""

from typing import Any, Optional

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from odoo_manager.exceptions import PostgresConnectionError


def get_postgres_connection(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
    database: str = "postgres",
):
    """Get a PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except psycopg2.Error as e:
        raise PostgresConnectionError(f"Failed to connect to PostgreSQL: {e}")


def list_databases(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
    exclude_template: bool = True,
) -> list[dict[str, Any]]:
    """List all databases."""
    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT datname, pg_size_pretty(pg_database_size(datname)) as size, "
            "pg_encoding_to_char(encoding) as encoding "
            "FROM pg_database "
            "ORDER BY datname"
        )
        results = cursor.fetchall()

        databases = []
        for row in results:
            name, size, encoding = row
            if exclude_template and name.startswith("template"):
                continue
            databases.append({
                "name": name,
                "size": size,
                "encoding": encoding,
            })

        return databases
    finally:
        cursor.close()
        conn.close()


def database_exists(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> bool:
    """Check if a database exists."""
    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()


def create_database(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
    template: str = "template1",
    encoding: str = "UTF8",
) -> None:
    """Create a new database."""
    if database_exists(name, host, port, user, password):
        raise ValueError(f"Database '{name}' already exists")

    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute(
            f'CREATE DATABASE "{name}" TEMPLATE = "{template}" ENCODING = \'{encoding}\''
        )
    finally:
        cursor.close()
        conn.close()


def drop_database(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> None:
    """Drop a database."""
    if not database_exists(name, host, port, user, password):
        raise ValueError(f"Database '{name}' does not exist")

    # Terminate connections first
    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{name}'"
        )
        cursor.execute(f'DROP DATABASE "{name}"')
    finally:
        cursor.close()
        conn.close()


def duplicate_database(
    source: str,
    target: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> None:
    """Duplicate a database."""
    if not database_exists(source, host, port, user, password):
        raise ValueError(f"Source database '{source}' does not exist")

    if database_exists(target, host, port, user, password):
        raise ValueError(f"Target database '{target}' already exists")

    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute(f'CREATE DATABASE "{target}" TEMPLATE = "{source}"')
    finally:
        cursor.close()
        conn.close()


def get_database_size(
    name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> Optional[str]:
    """Get the size of a database."""
    if not database_exists(name, host, port, user, password):
        return None

    conn = get_postgres_connection(host, port, user, password, database=name)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT pg_size_pretty(pg_database_size(%s))", (name,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()


def rename_database(
    old_name: str,
    new_name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> None:
    """Rename a database."""
    if not database_exists(old_name, host, port, user, password):
        raise ValueError(f"Database '{old_name}' does not exist")

    if database_exists(new_name, host, port, user, password):
        raise ValueError(f"Database '{new_name}' already exists")

    # Terminate connections first
    conn = get_postgres_connection(host, port, user, password)
    cursor = conn.cursor()

    try:
        cursor.execute(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{old_name}'"
        )
        cursor.execute(f'ALTER DATABASE "{old_name}" RENAME TO "{new_name}"')
    finally:
        cursor.close()
        conn.close()


def execute_sql(
    sql: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
    database: str = "postgres",
    fetch: bool = False,
) -> Optional[list[tuple]]:
    """Execute arbitrary SQL."""
    conn = get_postgres_connection(host, port, user, password, database)
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        if fetch:
            return cursor.fetchall()
        conn.commit()
        return None
    finally:
        cursor.close()
        conn.close()


def check_connection(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "",
) -> bool:
    """Check if PostgreSQL connection is possible.

    Args:
        host: Database host.
        port: Database port.
        user: Database user.
        password: Database password.

    Returns:
        True if connection successful.
    """
    try:
        conn = get_postgres_connection(host, port, user, password)
        conn.close()
        return True
    except Exception:
        return False
