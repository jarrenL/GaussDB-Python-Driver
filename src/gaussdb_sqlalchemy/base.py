"""Base SQLAlchemy dialect classes for GaussDB."""

from __future__ import annotations

import re

from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy import text


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
    postgresql_compat_version = (9, 2)

    def initialize(self, connection):
        super().initialize(connection)
        self.server_version_info = self._normalize_gaussdb_version(
            self.server_version_info
        )

    def _get_server_version_info(self, connection):
        version = connection.exec_driver_sql("select pg_catalog.version()").scalar()
        version = self._decode_if_bytes(version)

        gaussdb_version = self._match_version(version, "GaussDB Kernel")
        if gaussdb_version:
            self.gaussdb_server_version_info = gaussdb_version
            self.gaussdb_server_version_string = version
            return self.postgresql_compat_version

        postgres_version = self._match_version(version, "PostgreSQL|EnterpriseDB")
        if not postgres_version:
            raise AssertionError(
                "Could not determine GaussDB version from string '%s'" % version
            )
        return postgres_version

    def _get_default_schema_name(self, connection):
        schema_name = connection.exec_driver_sql("select current_schema()").scalar()
        return self._decode_if_bytes(schema_name)

    def get_columns(self, connection, table_name, schema=None, **kw):
        columns = dict(
            self.get_multi_columns(
                connection,
                schema=schema,
                filter_names=[table_name],
                scope=None,
                kind=None,
                **kw,
            )
        )
        key = (schema, table_name)
        if key not in columns:
            raise NoSuchTableError(table_name)
        return columns[key]

    def get_multi_columns(
        self, connection, schema=None, filter_names=None, scope=None, kind=None, **kw
    ):
        filter_names = tuple(filter_names or ())
        conditions = [
            "a.attnum > 0",
            "not a.attisdropped",
            "c.relkind in ('r', 'p', 'f', 'v', 'm')",
            "n.nspname != 'pg_catalog'",
        ]
        params = {}

        if schema:
            conditions.append("n.nspname = :schema")
            params["schema"] = schema
        else:
            conditions.append("pg_catalog.pg_table_is_visible(c.oid)")

        if filter_names:
            conditions.append("c.relname in :filter_names")
            params["filter_names"] = filter_names

        query = text(
            """
            select
                n.nspname as schema_name,
                c.relname as table_name,
                a.attname as name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) as format_type,
                a.attnotnull as not_null,
                pg_catalog.pg_get_expr(d.adbin, d.adrelid) as "default",
                pg_catalog.col_description(a.attrelid, a.attnum) as comment
            from pg_catalog.pg_class c
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            join pg_catalog.pg_attribute a on a.attrelid = c.oid
            left join pg_catalog.pg_attrdef d
                on d.adrelid = a.attrelid and d.adnum = a.attnum
            where
            """
            + " and ".join(conditions)
            + """
            order by c.relname, a.attnum
            """
        )
        if filter_names:
            query = query.bindparams(bindparam("filter_names", expanding=True))

        reflected = {}
        rows = connection.execute(query, params).mappings()
        for row in rows:
            table_name = self._decode_if_bytes(row["table_name"])
            schema_name = self._decode_if_bytes(row["schema_name"])
            key = (schema_name if schema else None, table_name)
            column_name = self._decode_if_bytes(row["name"])
            format_type = self._decode_if_bytes(row["format_type"])
            default = self._decode_if_bytes(row["default"])
            comment = self._decode_if_bytes(row["comment"])
            reflected.setdefault(key, []).append(
                {
                    "name": column_name,
                    "type": self._reflect_type(
                        format_type,
                        {},
                        {},
                        type_description=f"column '{column_name}'",
                        collation=None,
                    ),
                    "nullable": not row["not_null"],
                    "default": default,
                    "autoincrement": False,
                    "comment": comment,
                }
            )

        return reflected.items()

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        query = text(
            """
            select
                con.conname as name,
                a.attname as column_name,
                a.attnum as ordinality
            from pg_catalog.pg_constraint con
            join pg_catalog.pg_class c on c.oid = con.conrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            join pg_catalog.pg_attribute a
                on a.attrelid = c.oid and a.attnum = any(con.conkey)
            where con.contype = 'p'
              and c.relname = :table_name
              and (:schema is null or n.nspname = :schema)
            order by a.attnum
            """
        )
        rows = connection.execute(
            query, {"table_name": table_name, "schema": schema}
        ).mappings()
        constraint_name = None
        constrained_columns = []
        for row in rows:
            constraint_name = self._decode_if_bytes(row["name"])
            constrained_columns.append(self._decode_if_bytes(row["column_name"]))
        return {"constrained_columns": constrained_columns, "name": constraint_name}

    def get_unique_constraints(self, connection, table_name, schema=None, **kw):
        query = text(
            """
            select
                con.conname as name,
                a.attname as column_name,
                a.attnum as ordinality
            from pg_catalog.pg_constraint con
            join pg_catalog.pg_class c on c.oid = con.conrelid
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            join pg_catalog.pg_attribute a
                on a.attrelid = c.oid and a.attnum = any(con.conkey)
            where con.contype = 'u'
              and c.relname = :table_name
              and (:schema is null or n.nspname = :schema)
            order by con.conname, a.attnum
            """
        )
        rows = connection.execute(
            query, {"table_name": table_name, "schema": schema}
        ).mappings()
        constraints = {}
        for row in rows:
            name = self._decode_if_bytes(row["name"])
            constraints.setdefault(name, []).append(
                self._decode_if_bytes(row["column_name"])
            )
        return [
            {"name": name, "column_names": columns, "duplicates_index": None}
            for name, columns in constraints.items()
        ]

    def get_indexes(self, connection, table_name, schema=None, **kw):
        query = text(
            """
            select
                i.relname as index_name,
                a.attname as column_name,
                x.indisunique as is_unique,
                a.attnum as ordinality
            from pg_catalog.pg_class t
            join pg_catalog.pg_namespace n on n.oid = t.relnamespace
            join pg_catalog.pg_index x on x.indrelid = t.oid
            join pg_catalog.pg_class i on i.oid = x.indexrelid
            join pg_catalog.pg_attribute a
                on a.attrelid = t.oid and a.attnum = any(x.indkey)
            where t.relname = :table_name
              and (:schema is null or n.nspname = :schema)
              and not x.indisprimary
            order by i.relname, a.attnum
            """
        )
        rows = connection.execute(
            query, {"table_name": table_name, "schema": schema}
        ).mappings()
        indexes = {}
        for row in rows:
            name = self._decode_if_bytes(row["index_name"])
            index = indexes.setdefault(
                name,
                {
                    "name": name,
                    "unique": row["is_unique"],
                    "column_names": [],
                    "include_columns": [],
                    "dialect_options": {},
                },
            )
            index["column_names"].append(self._decode_if_bytes(row["column_name"]))
        return list(indexes.values())

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

    @staticmethod
    def _match_version(version, product_pattern):
        match = re.search(
            rf"(?:{product_pattern})\s+(\d+)\.?(\d+)?(?:\.(\d+))?",
            version,
            re.IGNORECASE,
        )
        if not match:
            return None
        return tuple(int(part) for part in match.group(1, 2, 3) if part is not None)
