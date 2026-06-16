"""SQLAlchemy support for Huawei GaussDB."""

from .alembic import register_alembic_impl
from .dialect import GaussDBDialect_gaussdb

register_alembic_impl()

__all__ = ["GaussDBDialect_gaussdb"]
__version__ = "0.1.0"
