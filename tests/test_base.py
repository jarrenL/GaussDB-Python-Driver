from gaussdb_sqlalchemy.base import GaussDBDialect


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, values):
        self.values = values

    def exec_driver_sql(self, statement):
        return _ScalarResult(self.values[statement])


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self.rows


class _ReflectionConnection:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.params = None

    def execute(self, statement, params):
        self.statement = statement
        self.params = params
        return _Rows(self.rows)


def test_dialect_identity_and_defaults():
    assert GaussDBDialect.name == "gaussdb"
    assert GaussDBDialect.default_paramstyle == "pyformat"
    assert GaussDBDialect.supports_statement_cache is True
    assert GaussDBDialect.use_native_hstore is False
    assert GaussDBDialect.postgresql_compat_version == (9, 2)


def test_normalize_gaussdb_version_keeps_integer_tuples():
    assert GaussDBDialect._normalize_gaussdb_version((5, 0, 5, 1)) == (5, 0, 5, 1)


def test_normalize_gaussdb_version_strips_non_numeric_suffixes():
    assert GaussDBDialect._normalize_gaussdb_version((5, "0.5", "505.1", "build")) == (
        5,
        0,
        505,
    )


def test_normalize_gaussdb_version_handles_empty_or_unknown_values():
    assert GaussDBDialect._normalize_gaussdb_version(None) is None
    assert GaussDBDialect._normalize_gaussdb_version(()) == ()
    assert GaussDBDialect._normalize_gaussdb_version(("GaussDB",)) == ("GaussDB",)


def test_get_server_version_info_supports_gaussdb_kernel_string():
    dialect = GaussDBDialect()
    connection = _Connection(
        {
            "select pg_catalog.version()": (
                b"gaussdb (GaussDB Kernel 507.0.0 build 1268bd4d) release"
            )
        }
    )

    assert dialect._get_server_version_info(connection) == (9, 2)
    assert dialect.gaussdb_server_version_info == (507, 0, 0)
    assert "GaussDB Kernel 507.0.0" in dialect.gaussdb_server_version_string


def test_get_server_version_info_supports_postgresql_compatible_string():
    dialect = GaussDBDialect()
    connection = _Connection({"select pg_catalog.version()": "PostgreSQL 9.2.4"})

    assert dialect._get_server_version_info(connection) == (9, 2, 4)


def test_get_server_version_info_rejects_unknown_version_format():
    dialect = GaussDBDialect()
    connection = _Connection({"select pg_catalog.version()": "unknown database"})

    try:
        dialect._get_server_version_info(connection)
    except AssertionError as exc:
        assert "Could not determine GaussDB version" in str(exc)
    else:
        raise AssertionError("expected unknown version format to fail")


def test_get_default_schema_name_decodes_bytes():
    dialect = GaussDBDialect()
    connection = _Connection({"select current_schema()": b"public"})

    assert dialect._get_default_schema_name(connection) == "public"


def test_get_columns_uses_gaussdb_compatible_reflection_query():
    dialect = GaussDBDialect()
    connection = _ReflectionConnection(
        [
            {
                "schema_name": b"public",
                "table_name": b"demo",
                "name": b"id",
                "format_type": b"integer",
                "not_null": True,
                "default": None,
                "comment": None,
            },
            {
                "schema_name": b"public",
                "table_name": b"demo",
                "name": b"name",
                "format_type": b"character varying(32)",
                "not_null": False,
                "default": None,
                "comment": b"display name",
            },
        ]
    )

    columns = dialect.get_columns(connection, "demo")

    assert [column["name"] for column in columns] == ["id", "name"]
    assert columns[0]["nullable"] is False
    assert columns[1]["nullable"] is True
    assert columns[1]["comment"] == "display name"
    assert connection.params == {"filter_names": ("demo",)}
    assert dict(dialect.get_multi_columns(connection, filter_names=["demo"])).get(
        (None, "demo")
    )
