"""Alembic DDL integration for the GaussDB SQLAlchemy dialect."""

from __future__ import annotations


_REGISTERED = False


def register_alembic_impl() -> bool:
    """Register GaussDB with Alembic when Alembic is installed."""

    global _REGISTERED
    if _REGISTERED:
        return True

    try:
        from alembic.ddl.postgresql import PostgresqlImpl
    except Exception:
        return False

    class GaussDBImpl(PostgresqlImpl):
        __dialect__ = "gaussdb"

    _REGISTERED = True
    return True
