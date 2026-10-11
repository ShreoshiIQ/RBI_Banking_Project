"""Provision the non-owner API role that row-level security policies apply to."""

import re

from psycopg import sql
from sqlalchemy import text


def provision(engine, role: str, password: str) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{2,62}", role):
        raise ValueError("Role must be a lowercase SQL identifier")
    with engine.begin() as conn:
        raw = conn.connection.driver_connection
        exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
        database = conn.execute(text("SELECT current_database()")).scalar()
        ident = sql.Identifier(role)
        # DDL cannot take bind parameters; psycopg quotes the identifier and password literal.
        statements = [
            sql.SQL("{} ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                sql.SQL("ALTER" if exists else "CREATE"), ident, sql.Literal(password)),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), ident),
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident),
            sql.SQL("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {}").format(ident),
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(ident),
            sql.SQL("REVOKE ALL ON alembic_version FROM {}").format(ident),
        ]
        for statement in statements:
            conn.exec_driver_sql(statement.as_string(raw))
