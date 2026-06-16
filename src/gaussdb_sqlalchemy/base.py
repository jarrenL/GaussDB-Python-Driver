"""Base SQLAlchemy dialect classes for GaussDB."""

from __future__ import annotations

import re

from sqlalchemy.dialects.postgresql.base import PGDialect


class GaussDBDialect(PGDialect):
    """PostgreSQL-compatible SQLAlchemy dialect for GaussDB.

    GaussDB centralized 505.1 is close enough to PostgreSQL for SQLAlchemy's
    PostgreSQL compiler and reflection base to be useful, but this class keeps
    the dialect name distinct and avoids PostgreSQL extension assumptions.
    """

    name = "gaussdb"
    supports_statement_cache = True
    supports_native_enum = True
    supports_native_boolean = True
    supports_smallserial = True
    supports_sequences = True
    sequences_optional = True
    postfetch_lastrowid = False
    default_paramstyle = "pyformat"

    # HSTORE is a PostgreSQL extension and should not be assumed for a minimal
    # GaussDB 505.1 centralized install.
    use_native_hstore = False

    def initialize(self, connection):
        super().initialize(connection)
        self.server_version_info = self._normalize_gaussdb_version(
            self.server_version_info
        )

    def _get_server_version_info(self, connection):
        version = connection.exec_driver_sql("select pg_catalog.version()").scalar()
        version = self._decode_if_bytes(version)

        match = re.search(
            r"(?:GaussDB Kernel|PostgreSQL|EnterpriseDB)\s+"
            r"(\d+)\.?(\d+)?(?:\.(\d+))?",
            version,
            re.IGNORECASE,
        )
        if not match:
            raise AssertionError(
                "Could not determine GaussDB version from string '%s'" % version
            )
        return tuple(int(part) for part in match.group(1, 2, 3) if part is not None)

    def _get_default_schema_name(self, connection):
        schema_name = connection.exec_driver_sql("select current_schema()").scalar()
        return self._decode_if_bytes(schema_name)

    @staticmethod
    def _normalize_gaussdb_version(version_info):
        if not version_info:
            return version_info

        normalized = []
        for part in version_info:
            if isinstance(part, int):
                normalized.append(part)
                continue
            try:
                normalized.append(int(str(part).split(".")[0]))
            except (TypeError, ValueError):
                break
        return tuple(normalized) or version_info

    @staticmethod
    def _decode_if_bytes(value):
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value
