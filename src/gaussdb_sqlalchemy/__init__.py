"""SQLAlchemy support for Huawei GaussDB."""

from .alembic import register_alembic_impl
from .jdbc import GaussDBDialect_jdbc

register_alembic_impl()

__all__ = ["GaussDBDialect_jdbc"]
__version__ = "0.1.0"
