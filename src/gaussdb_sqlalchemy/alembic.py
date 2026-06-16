"""Alembic DDL integration for the GaussDB SQLAlchemy dialect."""

from __future__ import annotations


def register_alembic_impl() -> bool:
    """Register GaussDB with Alembic when Alembic is installed."""

    try:
        from alembic.ddl.postgresql import PostgresqlImpl
    except Exception:
        return False

    class GaussDBImpl(PostgresqlImpl):
        __dialect__ = "gaussdb"

    return True
